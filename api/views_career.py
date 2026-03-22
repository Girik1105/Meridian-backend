import json

import anthropic
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .context_builder import _load_prompt
from .models import CareerPath
from .serializers import CareerPathSerializer


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def career_path_generate(request):
    profile = request.user.profile
    if not profile.onboarding_completed:
        return Response({"detail": "Complete onboarding first."}, status=400)

    # Return existing paths if already generated (skip expensive AI call)
    force = request.query_params.get("force") == "true"
    existing = CareerPath.objects.filter(user=request.user)
    if existing.exists() and not force:
        return Response(CareerPathSerializer(existing, many=True).data, status=200)

    profile_data = profile.profile_data or {}
    system_prompt = _load_prompt("career_discovery").format(
        profile_data=json.dumps(profile_data, indent=2),
        location=profile_data.get("constraints", {}).get("location", "United States"),
    )

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        system=system_prompt,
        messages=[{"role": "user", "content": "Generate career paths based on my profile."}],
    )

    try:
        paths_data = json.loads(response.content[0].text)
    except (json.JSONDecodeError, IndexError):
        return Response({"detail": "Failed to parse career paths from AI response."}, status=502)

    CareerPath.objects.filter(user=request.user).delete()
    created = []
    for cp in paths_data:
        path = CareerPath.objects.create(
            user=request.user,
            title=cp["title"],
            description=cp["description"],
            required_skills=cp.get("required_skills", []),
            estimated_timeline_months=cp.get("estimated_timeline_months", 0),
            salary_range=cp.get("salary_range", {}),
            match_reasoning=cp.get("match_reasoning", ""),
            relevance_score=cp.get("relevance_score", 0.0),
            roi_data=cp.get("roi_data", {}),
        )
        created.append(path)

    return Response(CareerPathSerializer(created, many=True).data, status=201)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def career_path_list(request):
    paths = CareerPath.objects.filter(user=request.user)

    sort_by = request.query_params.get("sort_by")
    if sort_by == "roi_score":
        paths = sorted(paths, key=lambda p: p.roi_data.get("roi_score", 0), reverse=True)
    elif sort_by == "lowest_investment":
        paths = sorted(paths, key=lambda p: p.roi_data.get("learning_time_hours", 9999))
    elif sort_by == "fastest":
        paths = sorted(paths, key=lambda p: p.estimated_timeline_months)

    serializer = CareerPathSerializer(paths, many=True)
    return Response(serializer.data)


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
