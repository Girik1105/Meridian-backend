from rest_framework import serializers

from .models import User, UserProfile, Conversation, Message, CareerPath, SkillTaster, TasterResponse


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ["id", "profile_data", "onboarding_completed", "journey_stage", "profile_version", "created_at", "updated_at"]
        read_only_fields = fields


class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "created_at", "updated_at", "profile"]
        read_only_fields = fields


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
        )


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ["id", "role", "content", "metadata", "created_at"]
        read_only_fields = fields


class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = ["id", "conversation_type", "title", "summary", "is_active", "created_at", "updated_at"]
        read_only_fields = fields


class ConversationDetailSerializer(ConversationSerializer):
    messages = MessageSerializer(many=True, read_only=True)

    class Meta(ConversationSerializer.Meta):
        fields = ConversationSerializer.Meta.fields + ["messages"]


class CareerPathSerializer(serializers.ModelSerializer):
    class Meta:
        model = CareerPath
        fields = [
            "id", "title", "description", "required_skills",
            "estimated_timeline_months", "salary_range", "match_reasoning",
            "relevance_score", "is_selected", "roi_data", "created_at", "updated_at",
        ]
        read_only_fields = fields


class TasterResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = TasterResponse
        fields = ["id", "module_id", "user_response", "time_spent_seconds", "created_at"]
        read_only_fields = fields


class SkillTasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = SkillTaster
        fields = [
            "id", "career_path", "skill_name", "taster_content",
            "status", "started_at", "completed_at", "created_at", "updated_at",
        ]
        read_only_fields = fields


class SkillTasterDetailSerializer(SkillTasterSerializer):
    responses = TasterResponseSerializer(many=True, read_only=True)
    assessment = serializers.JSONField(read_only=True)

    class Meta(SkillTasterSerializer.Meta):
        fields = SkillTasterSerializer.Meta.fields + ["responses", "assessment"]


class TasterGenerateSerializer(serializers.Serializer):
    career_path_id = serializers.UUIDField(required=True)
    skill_name = serializers.CharField(required=True)


class TasterRespondSerializer(serializers.Serializer):
    module_id = serializers.CharField(required=True)
    user_response = serializers.CharField(required=True)
    time_spent_seconds = serializers.IntegerField(default=0)


class ChatSendSerializer(serializers.Serializer):
    conversation_id = serializers.UUIDField(required=False, allow_null=True)
    conversation_type = serializers.ChoiceField(choices=Conversation.CONVERSATION_TYPES)
    message = serializers.CharField()
