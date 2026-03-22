from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .emails import send_password_reset_email
from .generation_utils import recover_stuck_generations
from .models import CareerPath, Conversation, SkillTaster
from .serializers import RegisterSerializer, UserSerializer, UserProfileSerializer

COOKIE_DEFAULTS = {
    "httponly": True,
    "secure": not settings.DEBUG,
    "samesite": "None" if not settings.DEBUG else "Lax",
    "path": "/",
}


def _set_auth_cookies(response, refresh):
    access_lifetime = settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"]
    refresh_lifetime = settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]

    response.set_cookie(
        "access",
        str(refresh.access_token),
        max_age=int(access_lifetime.total_seconds()),
        **COOKIE_DEFAULTS,
    )
    response.set_cookie(
        "refresh",
        str(refresh),
        max_age=int(refresh_lifetime.total_seconds()),
        **COOKIE_DEFAULTS,
    )
    return response


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()

    refresh = RefreshToken.for_user(user)
    response = Response(
        {
            "user": UserSerializer(user).data,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        },
        status=status.HTTP_201_CREATED,
    )
    return _set_auth_cookies(response, refresh)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def login(request):
    from django.contrib.auth import authenticate

    username = request.data.get("username")
    password = request.data.get("password")

    if not username or not password:
        return Response(
            {"detail": "Username and password are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = authenticate(username=username, password=password)
    if user is None:
        return Response(
            {"detail": "Invalid credentials."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    refresh = RefreshToken.for_user(user)
    response = Response({
        "user": UserSerializer(user).data,
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    })
    return _set_auth_cookies(response, refresh)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def refresh(request):
    # Accept refresh token from body or cookie
    raw_refresh = request.data.get("refresh") or request.COOKIES.get("refresh")
    if not raw_refresh:
        return Response(
            {"detail": "No refresh token."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    try:
        old_refresh = RefreshToken(raw_refresh)
        old_refresh.check_exp()
    except TokenError:
        return Response(
            {"detail": "Invalid or expired refresh token."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        user = User.objects.get(id=old_refresh.payload.get("user_id"))
    except User.DoesNotExist:
        return Response(
            {"detail": "User not found."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    new_refresh = RefreshToken.for_user(user)
    response = Response({
        "detail": "Token refreshed.",
        "access": str(new_refresh.access_token),
        "refresh": str(new_refresh),
    })
    return _set_auth_cookies(response, new_refresh)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def logout(request):
    response = Response({"detail": "Logged out."})
    response.delete_cookie("access", path="/")
    response.delete_cookie("refresh", path="/")
    return response


@api_view(["POST"])
@permission_classes([AllowAny])
def forgot_password(request):
    email = request.data.get("email")
    if not email:
        return Response(
            {"detail": "Email is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    User = get_user_model()
    try:
        user = User.objects.get(email=email)
        send_password_reset_email(user)
    except User.DoesNotExist:
        pass  # Don't reveal whether the email exists

    return Response(
        {"detail": "If an account with that email exists, a reset link has been sent."}
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def reset_password(request):
    uid = request.data.get("uid")
    token = request.data.get("token")
    new_password = request.data.get("new_password")

    if not uid or not token or not new_password:
        return Response(
            {"detail": "uid, token, and new_password are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if len(new_password) < 8:
        return Response(
            {"detail": "Password must be at least 8 characters."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    User = get_user_model()
    try:
        user_id = urlsafe_base64_decode(uid).decode()
        user = User.objects.get(pk=user_id)
    except (ValueError, TypeError, User.DoesNotExist):
        return Response(
            {"detail": "Invalid reset link."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not default_token_generator.check_token(user, token):
        return Response(
            {"detail": "Reset link has expired or is invalid."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user.set_password(new_password)
    user.save()

    return Response({"detail": "Password has been reset successfully."})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    return Response(UserSerializer(request.user).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def profile(request):
    return Response(UserProfileSerializer(request.user.profile).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def session_state(request):
    """Unified snapshot of user's current state for frontend restoration."""
    recover_stuck_generations(request.user)

    profile = request.user.profile
    profile.refresh_from_db()

    # Active conversation (most recent)
    active_conv = Conversation.objects.filter(
        user=request.user, is_active=True
    ).order_by("-updated_at").first()

    active_conversation = None
    if active_conv:
        active_conversation = {
            "id": str(active_conv.id),
            "conversation_type": active_conv.conversation_type,
            "title": active_conv.title,
        }

    # Career paths status
    career_paths_count = CareerPath.objects.filter(user=request.user).count()
    if profile.journey_stage == "generating_paths":
        career_paths_status = "generating"
    elif career_paths_count > 0:
        career_paths_status = "ready"
    else:
        career_paths_status = "none"

    # Selected career path
    selected_path = CareerPath.objects.filter(
        user=request.user, is_selected=True
    ).first()
    selected_career_path = None
    if selected_path:
        selected_career_path = {
            "id": str(selected_path.id),
            "title": selected_path.title,
        }

    # Pending tasters (still generating)
    pending_tasters = list(
        SkillTaster.objects.filter(
            user=request.user, status="generating"
        ).values("id", "skill_name", "status", "created_at")
    )
    for t in pending_tasters:
        t["id"] = str(t["id"])

    # Active taster (in progress)
    active_taster_obj = SkillTaster.objects.filter(
        user=request.user, status="in_progress"
    ).first()
    active_taster = None
    if active_taster_obj:
        active_taster = {
            "id": str(active_taster_obj.id),
            "skill_name": active_taster_obj.skill_name,
            "started_at": active_taster_obj.started_at,
        }

    # Failed tasters (can be retried)
    failed_tasters = list(
        SkillTaster.objects.filter(
            user=request.user, status="generation_failed"
        ).values("id", "skill_name", "status")
    )
    for t in failed_tasters:
        t["id"] = str(t["id"])

    return Response({
        "journey_stage": profile.journey_stage,
        "onboarding_completed": profile.onboarding_completed,
        "active_conversation": active_conversation,
        "career_paths_status": career_paths_status,
        "career_paths_count": career_paths_count,
        "selected_career_path": selected_career_path,
        "pending_tasters": pending_tasters,
        "active_taster": active_taster,
        "failed_tasters": failed_tasters,
    })
