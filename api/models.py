import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "users"


JOURNEY_STAGES = [
    ("onboarding", "Onboarding"),
    ("generating_paths", "Generating Paths"),
    ("career_discovery", "Career Discovery"),
    ("skill_taster", "Skill Taster"),
]


class UserProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    profile_data = models.JSONField(default=dict)
    onboarding_completed = models.BooleanField(default=False)
    journey_stage = models.CharField(max_length=20, choices=JOURNEY_STAGES, default="onboarding")
    profile_version = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_profiles"

    def __str__(self):
        return f"Profile for {self.user.username}"


class Conversation(models.Model):
    CONVERSATION_TYPES = [
        ("onboarding", "Onboarding"),
        ("career_discovery", "Career Discovery"),
        ("skill_taster", "Skill Taster"),
        ("mentor_chat", "Mentor Chat"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="conversations")
    conversation_type = models.CharField(max_length=20, choices=CONVERSATION_TYPES)
    title = models.CharField(max_length=255, blank=True, default="")
    summary = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "conversations"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.conversation_type} - {self.user.username}"


class Message(models.Model):
    ROLE_CHOICES = [
        ("user", "User"),
        ("assistant", "Assistant"),
        ("system", "System"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "messages"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.role}: {self.content[:50]}"


class CareerPath(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="career_paths")
    title = models.CharField(max_length=255)
    description = models.TextField()
    required_skills = models.JSONField(default=list)
    estimated_timeline_months = models.IntegerField()
    salary_range = models.JSONField(default=dict)
    match_reasoning = models.TextField()
    relevance_score = models.FloatField()
    is_selected = models.BooleanField(default=False)
    roi_data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "career_paths"
        ordering = ["-relevance_score"]

    def __str__(self):
        return f"{self.title} - {self.user.username}"


class SkillTaster(models.Model):
    STATUS_CHOICES = [
        ("generating", "Generating"),
        ("not_started", "Not Started"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("generation_failed", "Generation Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="skill_tasters")
    career_path = models.ForeignKey(
        CareerPath, on_delete=models.SET_NULL, null=True, blank=True, related_name="skill_tasters"
    )
    skill_name = models.CharField(max_length=255)
    taster_content = models.JSONField(default=dict)
    assessment = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="not_started")
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "skill_tasters"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.skill_name} - {self.user.username}"


class TasterResponse(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    skill_taster = models.ForeignKey(SkillTaster, on_delete=models.CASCADE, related_name="responses")
    module_id = models.CharField(max_length=50)
    user_response = models.TextField()
    time_spent_seconds = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "taster_responses"
        unique_together = [("skill_taster", "module_id")]

    def __str__(self):
        return f"{self.skill_taster.skill_name} - {self.module_id}"
