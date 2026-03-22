import logging
from datetime import timedelta

from django.utils import timezone

from .models import SkillTaster, UserProfile

logger = logging.getLogger(__name__)

GENERATION_TIMEOUT = timedelta(minutes=5)


def recover_stuck_generations(user):
    """Detect and recover stuck generations for a user.

    Called lazily on GET requests so the frontend always gets accurate status.
    """
    now = timezone.now()
    cutoff = now - GENERATION_TIMEOUT

    # Stuck tasters: status="generating" and created_at older than timeout
    stuck_tasters = SkillTaster.objects.filter(
        user=user,
        status="generating",
        created_at__lt=cutoff,
    ).update(
        status="generation_failed",
        taster_content={"error": "Generation timed out. Please retry."},
    )

    # Stuck career path generation: journey_stage="generating_paths" and updated_at older than timeout
    stuck_profiles = UserProfile.objects.filter(
        user=user,
        journey_stage="generating_paths",
        updated_at__lt=cutoff,
    ).update(journey_stage="career_discovery")

    recovered = stuck_tasters + stuck_profiles
    if recovered:
        logger.info("Recovered %d stuck generations for user %s", recovered, user.id)

    return recovered
