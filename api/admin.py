from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User, UserProfile, Conversation, Message, CareerPath, SkillTaster, TasterResponse


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["username", "email", "is_staff", "created_at"]
    ordering = ["-created_at"]


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "onboarding_completed", "journey_stage", "profile_version", "updated_at"]
    list_filter = ["journey_stage", "onboarding_completed"]


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ["user", "conversation_type", "title", "is_active", "updated_at"]
    list_filter = ["conversation_type", "is_active"]


@admin.register(CareerPath)
class CareerPathAdmin(admin.ModelAdmin):
    list_display = ["title", "user", "relevance_score", "is_selected", "created_at"]
    list_filter = ["is_selected"]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["conversation", "role", "created_at"]
    list_filter = ["role"]


@admin.register(SkillTaster)
class SkillTasterAdmin(admin.ModelAdmin):
    list_display = ["skill_name", "user", "career_path", "status", "created_at"]
    list_filter = ["status"]


@admin.register(TasterResponse)
class TasterResponseAdmin(admin.ModelAdmin):
    list_display = ["skill_taster", "module_id", "time_spent_seconds", "created_at"]
