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

    cookie_kwargs = {**COOKIE_DEFAULTS}
    if not settings.DEBUG:
        cookie_kwargs["partitioned"] = True

    response.set_cookie(
        "access",
        str(refresh.access_token),
        max_age=int(access_lifetime.total_seconds()),
        **cookie_kwargs,
    )
    response.set_cookie(
        "refresh",
        str(refresh),
        max_age=int(refresh_lifetime.total_seconds()),
        **cookie_kwargs,
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
        {"user": UserSerializer(user).data},
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
    response = Response({"user": UserSerializer(user).data})
    return _set_auth_cookies(response, refresh)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def refresh(request):
    raw_refresh = request.COOKIES.get("refresh")
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
    response = Response({"detail": "Token refreshed."})
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
