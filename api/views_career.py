import json
import logging
import threading

import anthropic
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .context_builder import _load_prompt
from .generation_utils import recover_stuck_generations
from .models import CareerPath
from .serializers import CareerPathSerializer

logger = logging.getLogger(__name__)


def _generate_career_paths(user_id, system_prompt):
    """Background thread: call Claude and create CareerPath records."""
    from .models import User

    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            system=system_prompt,
            messages=[{"role": "user", "content": "Generate career paths based on my profile."}],
        )

        paths_data = json.loads(response.content[0].text)

        CareerPath.objects.filter(user_id=user_id).delete()
        for cp in paths_data:
            CareerPath.objects.create(
                user_id=user_id,
                title=cp["title"],
                description=cp["description"],
                required_skills=cp.get("required_skills", []),
                estimated_timeline_months=cp.get("estimated_timeline_months", 0),
                salary_range=cp.get("salary_range", {}),
                match_reasoning=cp.get("match_reasoning", ""),
                relevance_score=cp.get("relevance_score", 0.0),
                roi_data=cp.get("roi_data", {}),
            )

        # Update journey stage
        user = User.objects.get(id=user_id)
        profile = user.profile
        if profile.journey_stage == "generating_paths":
            profile.journey_stage = "career_discovery"
            profile.save(update_fields=["journey_stage", "updated_at"])

    except Exception:
        logger.exception("Failed to generate career paths for user %s", user_id)
        # Reset journey stage so user can retry
        try:
            user = User.objects.get(id=user_id)
            profile = user.profile
            if profile.journey_stage == "generating_paths":
                profile.journey_stage = "career_discovery"
                profile.save(update_fields=["journey_stage", "updated_at"])
        except Exception:
            pass


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def career_path_generate(request):
    recover_stuck_generations(request.user)

    profile = request.user.profile
    profile.refresh_from_db()

    if not profile.onboarding_completed:
        return Response({"detail": "Complete onboarding first."}, status=400)

    # Return existing paths if already generated (skip expensive AI call)
    force = request.query_params.get("force") == "true"
    existing = CareerPath.objects.filter(user=request.user)
    if existing.exists() and not force:
        return Response(CareerPathSerializer(existing, many=True).data, status=200)

    # Check if already generating
    if profile.journey_stage == "generating_paths":
        return Response({"status": "generating"}, status=202)

    profile_data = profile.profile_data or {}
    system_prompt = _load_prompt("career_discovery").format(
        profile_data=json.dumps(profile_data, indent=2),
        location=profile_data.get("constraints", {}).get("location", "United States"),
    )

    # Mark as generating and kick off background thread
    profile.journey_stage = "generating_paths"
    profile.save(update_fields=["journey_stage", "updated_at"])

    thread = threading.Thread(
        target=_generate_career_paths,
        args=(request.user.id, system_prompt),
        daemon=True,
    )
    thread.start()

    return Response({"status": "generating"}, status=202)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def career_path_list(request):
    recover_stuck_generations(request.user)

    profile = request.user.profile
    profile.refresh_from_db()

    paths = CareerPath.objects.filter(user=request.user)

    sort_by = request.query_params.get("sort_by")
    if sort_by == "roi_score":
        paths = sorted(paths, key=lambda p: p.roi_data.get("roi_score", 0), reverse=True)
    elif sort_by == "lowest_investment":
        paths = sorted(paths, key=lambda p: p.roi_data.get("learning_time_hours", 9999))
    elif sort_by == "fastest":
        paths = sorted(paths, key=lambda p: p.estimated_timeline_months)

    # Determine generation status
    if profile.journey_stage == "generating_paths":
        generation_status = "generating"
    elif isinstance(paths, list):
        generation_status = "ready" if paths else "none"
    else:
        generation_status = "ready" if paths.exists() else "none"

    serializer = CareerPathSerializer(paths, many=True)
    return Response({
        "generation_status": generation_status,
        "paths": serializer.data,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def career_path_select(request, pk):
    try:
        career_path = CareerPath.objects.get(id=pk, user=request.user)
    except CareerPath.DoesNotExist:
        return Response({"detail": "Career path not found."}, status=404)

    CareerPath.objects.filter(user=request.user).update(is_selected=False)
    career_path.is_selected = True
    career_path.save(update_fields=["is_selected", "updated_at"])

    # Advance journey stage only if not already at skill_taster
    profile = request.user.profile
    if profile.journey_stage != "skill_taster":
        profile.journey_stage = "skill_taster"
        profile.save(update_fields=["journey_stage", "updated_at"])

    serializer = CareerPathSerializer(career_path)
    return Response(serializer.data)
