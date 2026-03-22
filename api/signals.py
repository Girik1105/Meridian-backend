from django.db.models.signals import post_save
from django.dispatch import receiver

from .emails import send_welcome_email
from .models import User, UserProfile


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
        send_welcome_email(instance)
