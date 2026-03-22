from django.urls import path

from . import views_auth, views_career, views_conversations, views_taster
from .views_chat import ChatSendView, chat_stream_view

urlpatterns = [
    # Auth
    path("auth/register/", views_auth.register, name="auth-register"),
    path("auth/login/", views_auth.login, name="auth-login"),
    path("auth/refresh/", views_auth.refresh, name="auth-refresh"),
    path("auth/logout/", views_auth.logout, name="auth-logout"),
    path("auth/me/", views_auth.me, name="auth-me"),
    path("auth/forgot-password/", views_auth.forgot_password, name="auth-forgot-password"),
    path("auth/reset-password/", views_auth.reset_password, name="auth-reset-password"),

    # Profile & Session State
    path("profile/", views_auth.profile, name="profile"),
    path("session-state/", views_auth.session_state, name="session-state"),

    # Chat
    path("chat/send/", ChatSendView.as_view(), name="chat-send"),
    path("chat/stream/<uuid:conversation_id>/", chat_stream_view, name="chat-stream"),

    # Career Paths
    path("career-paths/", views_career.career_path_list, name="career-path-list"),
    path("career-paths/generate/", views_career.career_path_generate, name="career-path-generate"),
    path("career-paths/<uuid:pk>/select/", views_career.career_path_select, name="career-path-select"),

    # Skill Tasters
    path("tasters/", views_taster.taster_list, name="taster-list"),
    path("tasters/generate/", views_taster.taster_generate, name="taster-generate"),
    path("tasters/<uuid:pk>/", views_taster.taster_detail, name="taster-detail"),
    path("tasters/<uuid:pk>/start/", views_taster.taster_start, name="taster-start"),
    path("tasters/<uuid:pk>/respond/", views_taster.taster_respond, name="taster-respond"),
    path("tasters/<uuid:pk>/complete/", views_taster.taster_complete, name="taster-complete"),
    path("tasters/<uuid:pk>/retry/", views_taster.taster_retry, name="taster-retry"),
    path("tasters/<uuid:pk>/assessment/", views_taster.taster_assessment, name="taster-assessment"),

    # Conversations
    path("conversations/", views_conversations.conversation_list, name="conversation-list"),
    path("conversations/<uuid:pk>/", views_conversations.conversation_detail, name="conversation-detail"),
]
