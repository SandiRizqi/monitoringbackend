# data/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import HotspotAlert, DeforestationAlerts
from notifications.services import NotificationService

@receiver(post_save, sender=HotspotAlert)
def send_hotspot_notification(sender, instance, created, **kwargs):
    """Trigger notifikasi ketika hotspot alert baru dibuat"""
    if created:
        NotificationService.send_hotspot_notification(instance)

@receiver(post_save, sender=DeforestationAlerts)
def send_deforestation_notification(sender, instance, created, **kwargs):
    """Trigger notifikasi ketika deforestation alert baru dibuat"""
    if created:
        NotificationService.send_deforestation_notification(instance)
