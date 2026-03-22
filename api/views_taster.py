import json
import logging
import threading

import anthropic
from django.conf import settings
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .context_builder import ContextBuilder
from .generation_utils import GENERATION_TIMEOUT, recover_stuck_generations
from .models import CareerPath, SkillTaster, TasterResponse
from .serializers import (
    SkillTasterDetailSerializer,
    SkillTasterSerializer,
    TasterGenerateSerializer,
    TasterRespondSerializer,
)

logger = logging.getLogger(__name__)


def _generate_taster_content(taster_id, system_prompt, skill_name):
    """Background thread: call Claude and update the taster record."""
    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            system=system_prompt,
            messages=[
                {"role": "user", "content": f"Generate a 30-minute skill taster for: {skill_name}"}
            ],
        )

        taster_content = json.loads(response.content[0].text)

        SkillTaster.objects.filter(id=taster_id).update(
            taster_content=taster_content,
            status="not_started",
        )
    except Exception:
        logger.exception("Failed to generate taster %s", taster_id)
        SkillTaster.objects.filter(id=taster_id).update(
            status="generation_failed",
            taster_content={"error": "Failed to generate skill taster. Please try again."},
        )


def _generate_assessment(taster_id, system_prompt):
    """Background thread: call Claude for assessment and update the taster record."""
    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        ai_response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system=system_prompt,
            messages=[
                {"role": "user", "content": "Generate an honest assessment of my skill taster performance."}
            ],
        )

        assessment = json.loads(ai_response.content[0].text)

        SkillTaster.objects.filter(id=taster_id).update(
            assessment=assessment,
        )
    except Exception:
        logger.exception("Failed to generate assessment for taster %s", taster_id)
        SkillTaster.objects.filter(id=taster_id).update(
            assessment={"error": "Failed to generate assessment."},
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def taster_generate(request):
    serializer = TasterGenerateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    career_path_id = serializer.validated_data["career_path_id"]
    skill_name = serializer.validated_data["skill_name"]

    try:
        career_path = CareerPath.objects.get(
            id=career_path_id, user=request.user, is_selected=True
        )
    except CareerPath.DoesNotExist:
        return Response(
            {"detail": "Selected career path not found."}, status=404
        )

    # Dedup: check for existing taster with same skill + career_path + user
    existing = SkillTaster.objects.filter(
        user=request.user,
        career_path=career_path,
        skill_name=skill_name,
    ).first()

    if existing:
        if existing.status == "generating":
            return Response(
                {"id": str(existing.id), "status": "generating", "skill_name": skill_name},
                status=202,
            )
        elif existing.status == "generation_failed":
            existing.delete()
        elif existing.status in ("not_started", "in_progress", "completed"):
            return Response(SkillTasterSerializer(existing).data, status=200)

    profile = request.user.profile
    builder = ContextBuilder()
    system_prompt = builder.build_for_skill_taster(profile, career_path, skill_name)

    # Create taster immediately with "generating" status
    taster = SkillTaster.objects.create(
        user=request.user,
        career_path=career_path,
        skill_name=skill_name,
        taster_content={},
        status="generating",
    )

    # Kick off Claude call in background thread
    thread = threading.Thread(
        target=_generate_taster_content,
        args=(taster.id, system_prompt, skill_name),
        daemon=True,
    )
    thread.start()

    return Response(
        {"id": str(taster.id), "status": "generating", "skill_name": skill_name},
        status=202,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def taster_retry(request, pk):
    """Retry generation for a failed taster."""
    try:
        taster = SkillTaster.objects.get(id=pk, user=request.user)
    except SkillTaster.DoesNotExist:
        return Response({"detail": "Skill taster not found."}, status=404)

    if taster.status != "generation_failed":
        return Response(
            {"detail": "Only failed tasters can be retried."}, status=400
        )

    profile = request.user.profile
    builder = ContextBuilder()
    system_prompt = builder.build_for_skill_taster(
        profile, taster.career_path, taster.skill_name
    )

    taster.status = "generating"
    taster.taster_content = {}
    taster.save(update_fields=["status", "taster_content", "updated_at"])

    thread = threading.Thread(
        target=_generate_taster_content,
        args=(taster.id, system_prompt, taster.skill_name),
        daemon=True,
    )
    thread.start()

    return Response(
        {"id": str(taster.id), "status": "generating", "skill_name": taster.skill_name},
        status=202,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def taster_list(request):
    recover_stuck_generations(request.user)

    tasters = SkillTaster.objects.filter(user=request.user)

    career_path_id = request.query_params.get("career_path_id")
    if career_path_id:
        tasters = tasters.filter(career_path_id=career_path_id)

    return Response(SkillTasterSerializer(tasters, many=True).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def taster_detail(request, pk):
    recover_stuck_generations(request.user)

    try:
        taster = SkillTaster.objects.get(id=pk, user=request.user)
    except SkillTaster.DoesNotExist:
        return Response({"detail": "Skill taster not found."}, status=404)

    return Response(SkillTasterDetailSerializer(taster).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def taster_start(request, pk):
    try:
        taster = SkillTaster.objects.get(id=pk, user=request.user)
    except SkillTaster.DoesNotExist:
        return Response({"detail": "Skill taster not found."}, status=404)

    if taster.status != "not_started":
        return Response(
            {"detail": "Taster has already been started."}, status=400
        )

    taster.status = "in_progress"
    taster.started_at = timezone.now()
    taster.save(update_fields=["status", "started_at", "updated_at"])

    return Response(SkillTasterSerializer(taster).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def taster_respond(request, pk):
    try:
        taster = SkillTaster.objects.get(id=pk, user=request.user)
    except SkillTaster.DoesNotExist:
        return Response({"detail": "Skill taster not found."}, status=404)

    if taster.status != "in_progress":
        return Response(
            {"detail": "Taster must be in progress to submit responses."}, status=400
        )

    serializer = TasterRespondSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    module_id = serializer.validated_data["module_id"]
    modules = taster.taster_content.get("modules", [])
    valid_ids = {m["id"] for m in modules}
    if module_id not in valid_ids:
        return Response({"detail": "Invalid module_id."}, status=400)

    response_obj, _ = TasterResponse.objects.update_or_create(
        skill_taster=taster,
        module_id=module_id,
        defaults={
            "user_response": serializer.validated_data["user_response"],
            "time_spent_seconds": serializer.validated_data["time_spent_seconds"],
        },
    )

    return Response(
        {
            "id": str(response_obj.id),
            "module_id": response_obj.module_id,
            "user_response": response_obj.user_response,
            "time_spent_seconds": response_obj.time_spent_seconds,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def taster_complete(request, pk):
    try:
        taster = SkillTaster.objects.get(id=pk, user=request.user)
    except SkillTaster.DoesNotExist:
        return Response({"detail": "Skill taster not found."}, status=404)

    if taster.status != "in_progress":
        return Response(
            {"detail": "Taster must be in progress to complete."}, status=400
        )

    taster.status = "completed"
    taster.completed_at = timezone.now()
    taster.assessment = {"status": "generating"}
    taster.save(update_fields=["status", "completed_at", "assessment", "updated_at"])

    # Generate assessment in background
    profile = request.user.profile
    responses = list(taster.responses.all())
    builder = ContextBuilder()
    system_prompt = builder.build_for_assessment(profile, taster, responses)

    thread = threading.Thread(
        target=_generate_assessment,
        args=(taster.id, system_prompt),
        daemon=True,
    )
    thread.start()

    return Response(SkillTasterDetailSerializer(taster).data, status=202)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def taster_assessment(request, pk):
    try:
        taster = SkillTaster.objects.get(id=pk, user=request.user)
    except SkillTaster.DoesNotExist:
        return Response({"detail": "Skill taster not found."}, status=404)

    if taster.status != "completed":
        return Response(
            {"detail": "Taster must be completed to view assessment."}, status=400
        )

    # Check for stuck assessment generation
    if taster.assessment == {"status": "generating"} and taster.completed_at:
        if timezone.now() - taster.completed_at > GENERATION_TIMEOUT:
            taster.assessment = {"error": "Assessment generation timed out. Please retry."}
            taster.save(update_fields=["assessment", "updated_at"])

    if not taster.assessment:
        return Response({"detail": "Assessment not available."}, status=404)

    return Response(taster.assessment)
