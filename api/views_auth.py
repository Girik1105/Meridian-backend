from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .serializers import RegisterSerializer, UserSerializer

COOKIE_DEFAULTS = {
    "httponly": True,
    "secure": not settings.DEBUG,
    "samesite": "Lax",
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
@permission_classes([AllowAny])
def logout(request):
    response = Response({"detail": "Logged out."})
    response.delete_cookie("access", path="/")
    response.delete_cookie("refresh", path="/")
    return response


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    return Response(UserSerializer(request.user).data)
