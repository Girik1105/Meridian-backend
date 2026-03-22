import json

import anthropic
from django.conf import settings
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .context_builder import ContextBuilder
from .models import CareerPath, SkillTaster, TasterResponse
from .serializers import (
    SkillTasterDetailSerializer,
    SkillTasterSerializer,
    TasterGenerateSerializer,
    TasterRespondSerializer,
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

    profile = request.user.profile
    builder = ContextBuilder()
    system_prompt = builder.build_for_skill_taster(profile, career_path, skill_name)

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        system=system_prompt,
        messages=[
            {"role": "user", "content": f"Generate a 30-minute skill taster for: {skill_name}"}
        ],
    )

    try:
        taster_content = json.loads(response.content[0].text)
    except (json.JSONDecodeError, IndexError):
        return Response(
            {"detail": "Failed to parse skill taster from AI response."}, status=502
        )

    taster = SkillTaster.objects.create(
        user=request.user,
        career_path=career_path,
        skill_name=skill_name,
        taster_content=taster_content,
    )

    return Response(SkillTasterDetailSerializer(taster).data, status=201)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def taster_list(request):
    tasters = SkillTaster.objects.filter(user=request.user)

    career_path_id = request.query_params.get("career_path_id")
    if career_path_id:
        tasters = tasters.filter(career_path_id=career_path_id)

    return Response(SkillTasterSerializer(tasters, many=True).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def taster_detail(request, pk):
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

    # Generate assessment
    profile = request.user.profile
    responses = list(taster.responses.all())
    builder = ContextBuilder()
    system_prompt = builder.build_for_assessment(profile, taster, responses)

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    ai_response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        system=system_prompt,
        messages=[
            {"role": "user", "content": "Generate an honest assessment of my skill taster performance."}
        ],
    )

    try:
        taster.assessment = json.loads(ai_response.content[0].text)
    except (json.JSONDecodeError, IndexError):
        taster.assessment = {"error": "Failed to generate assessment."}

    taster.save(update_fields=["status", "completed_at", "assessment", "updated_at"])

    return Response(SkillTasterDetailSerializer(taster).data)


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

    if not taster.assessment:
        return Response({"detail": "Assessment not available."}, status=404)

    return Response(taster.assessment)
