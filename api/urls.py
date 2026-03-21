from django.urls import path

from . import views_auth, views_conversations
from .views_chat import ChatSendView, chat_stream_view

urlpatterns = [
    # Auth
    path("auth/register/", views_auth.register, name="auth-register"),
    path("auth/login/", views_auth.login, name="auth-login"),
    path("auth/refresh/", views_auth.refresh, name="auth-refresh"),
    path("auth/logout/", views_auth.logout, name="auth-logout"),
    path("auth/me/", views_auth.me, name="auth-me"),

    # Profile
    path("profile/", views_auth.profile, name="profile"),

    # Chat
    path("chat/send/", ChatSendView.as_view(), name="chat-send"),
    path("chat/stream/<uuid:conversation_id>/", chat_stream_view, name="chat-stream"),

    # Conversations
    path("conversations/", views_conversations.conversation_list, name="conversation-list"),
    path("conversations/<uuid:pk>/", views_conversations.conversation_detail, name="conversation-detail"),
]
