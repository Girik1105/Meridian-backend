from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import CareerPath
from .serializers import CareerPathSerializer


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def career_path_list(request):
    paths = CareerPath.objects.filter(user=request.user)
    serializer = CareerPathSerializer(paths, many=True)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def career_path_select(request, pk):
    try:
        career_path = CareerPath.objects.get(id=pk, user=request.user)
    except CareerPath.DoesNotExist:
        return Response(
            {"detail": "Career path not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    career_path.is_selected = True
    career_path.save(update_fields=["is_selected", "updated_at"])

    # Advance journey stage only if not already at skill_taster
    profile = request.user.profile
    if profile.journey_stage != "skill_taster":
        profile.journey_stage = "skill_taster"
        profile.save(update_fields=["journey_stage", "updated_at"])

    serializer = CareerPathSerializer(career_path)
    return Response(serializer.data)
