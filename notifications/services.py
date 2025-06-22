# notifications/services.py
import logging
import requests
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from accounts.models import Users, AccountNotificationSetting
from data.models import AreaOfInterest, HotspotAlert, DeforestationAlerts
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class NotificationService:
    
    @staticmethod
    def send_hotspot_notification(hotspot_alert: HotspotAlert):
        """Kirim notifikasi untuk hotspot alert baru"""
        try:
            # Ambil users yang memiliki AOI terkait
            aoi = hotspot_alert.area_of_interest
            users = aoi.users_aoi.all()
            
            for user in users:
                # Cek pengaturan notifikasi user
                notification_setting = getattr(user, 'notification_setting', None)
                if not notification_setting:
                    # Buat default setting jika belum ada
                    notification_setting = AccountNotificationSetting.objects.create(user=user)
                
                # Cek apakah user ingin menerima notifikasi hotspot
                if (notification_setting.push_notifications and 
                    notification_setting.notify_on_new_hotspot_data):
                    
                    NotificationService._send_hotspot_email(user, hotspot_alert, notification_setting)
                    NotificationService._send_webhook_notification(
                        notification_setting.webhook_url,
                        'hotspot',
                        hotspot_alert
                    )
                    
        except Exception as e:
            logger.error(f"Error sending hotspot notification: {str(e)}")
    
    @staticmethod
    def send_deforestation_notification(deforestation_alert: DeforestationAlerts):
        """Kirim notifikasi untuk deforestation alert baru"""
        try:
            # Ambil users yang memiliki AOI terkait
            aoi = deforestation_alert.company
            users = aoi.users_aoi.all()
            
            for user in users:
                # Cek pengaturan notifikasi user
                notification_setting = getattr(user, 'notification_setting', None)
                if not notification_setting:
                    notification_setting = AccountNotificationSetting.objects.create(user=user)
                
                # Cek apakah user ingin menerima notifikasi deforestation
                if (notification_setting.push_notifications and 
                    notification_setting.notify_on_new_deforestation_data):
                    
                    NotificationService._send_deforestation_email(user, deforestation_alert, notification_setting)
                    NotificationService._send_webhook_notification(
                        notification_setting.webhook_url,
                        'deforestation',
                        deforestation_alert
                    )
                    
        except Exception as e:
            logger.error(f"Error sending deforestation notification: {str(e)}")
    
    @staticmethod
    def _send_hotspot_email(user: Users, hotspot_alert: HotspotAlert, notification_setting: AccountNotificationSetting):
        """Kirim email notifikasi hotspot"""
        try:
            # Siapkan data untuk template
            context = {
                'user': user,
                'hotspot_alert': hotspot_alert,
                'aoi_name': hotspot_alert.area_of_interest.name,
                'alert_date': hotspot_alert.alert_date,
                'category': hotspot_alert.get_category_display(),
                'confidence': hotspot_alert.confidence,
                'distance': hotspot_alert.distance,
                'hotspot_location': {
                    'lat': hotspot_alert.hotspot.lat,
                    'lng': hotspot_alert.hotspot.long,
                } if hotspot_alert.hotspot else None
            }
            
            # Render email template
            subject = f"🔥 Hotspot Alert - {hotspot_alert.area_of_interest.name}"
            html_message = render_to_string('notifications/hotspot_email.html', context)
            plain_message = render_to_string('notifications/hotspot_email.txt', context)
            
            # Daftar email penerima
            recipient_emails = notification_setting.receivers_emails or [user.email]
            
            # Kirim email
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipient_emails,
                html_message=html_message,
                fail_silently=False
            )
            
            logger.info(f"Hotspot notification sent to {recipient_emails}")
            
        except Exception as e:
            logger.error(f"Error sending hotspot email: {str(e)}")
    
    @staticmethod
    def _send_deforestation_email(user: Users, deforestation_alert: DeforestationAlerts, notification_setting: AccountNotificationSetting):
        """Kirim email notifikasi deforestation"""
        try:
            # Siapkan data untuk template
            context = {
                'user': user,
                'deforestation_alert': deforestation_alert,
                'company_name': deforestation_alert.company.name,
                'alert_date': deforestation_alert.alert_date,
                'confidence': deforestation_alert.confidence,
                'area': deforestation_alert.area,
                'event_id': deforestation_alert.event_id
            }
            
            # Render email template
            subject = f"🌳 Deforestation Alert - {deforestation_alert.company.name}"
            html_message = render_to_string('notifications/deforestation_email.html', context)
            plain_message = render_to_string('notifications/deforestation_email.txt', context)
            
            # Daftar email penerima
            recipient_emails = notification_setting.receivers_emails or [user.email]
            
            # Kirim email
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipient_emails,
                html_message=html_message,
                fail_silently=False
            )
            
            logger.info(f"Deforestation notification sent to {recipient_emails}")
            
        except Exception as e:
            logger.error(f"Error sending deforestation email: {str(e)}")
    
    @staticmethod
    def _send_webhook_notification(webhook_url: str, notification_type: str, alert_data: Any):
        """Kirim notifikasi via webhook untuk sinkronisasi dengan sistem client"""
        if not webhook_url:
            return
            
        try:
            # Siapkan payload untuk webhook
            if notification_type == 'hotspot':
                payload = {
                    'type': 'hotspot_alert',
                    'timestamp': timezone.now().isoformat(),
                    'data': {
                        'alert_id': alert_data.id,
                        'aoi_id': str(alert_data.area_of_interest.id),
                        'aoi_name': alert_data.area_of_interest.name,
                        'alert_date': alert_data.alert_date.isoformat(),
                        'category': alert_data.category,
                        'confidence': alert_data.confidence,
                        'distance': float(alert_data.distance) if alert_data.distance else None,
                        'hotspot_id': alert_data.hotspot.id if alert_data.hotspot else None,
                        'coordinates': {
                            'lat': alert_data.hotspot.lat,
                            'lng': alert_data.hotspot.long
                        } if alert_data.hotspot else None
                    }
                }
            elif notification_type == 'deforestation':
                payload = {
                    'type': 'deforestation_alert',
                    'timestamp': timezone.now().isoformat(),
                    'data': {
                        'alert_id': alert_data.id,
                        'company_id': str(alert_data.company.id),
                        'company_name': alert_data.company.name,
                        'event_id': alert_data.event_id,
                        'alert_date': alert_data.alert_date.isoformat(),
                        'confidence': alert_data.confidence,
                        'area': float(alert_data.area) if alert_data.area else None
                    }
                }
            
            # Kirim POST request ke webhook URL
            response = requests.post(
                webhook_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"Webhook notification sent successfully to {webhook_url}")
            else:
                logger.warning(f"Webhook notification failed: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Error sending webhook notification: {str(e)}")
    
    @staticmethod
    def send_test_notification(user: Users, notification_type: str):
        """Kirim test notification untuk testing"""
        try:
            notification_setting = getattr(user, 'notification_setting', None)
            if not notification_setting:
                notification_setting = AccountNotificationSetting.objects.create(user=user)
            
            subject = f"🧪 Test Notification - {notification_type.title()}"
            context = {
                'user': user,
                'notification_type': notification_type,
                'test_time': timezone.now()
            }
            
            html_message = render_to_string('notifications/test_email.html', context)
            plain_message = f"Test notification for {notification_type} - {timezone.now()}"
            
            recipient_emails = notification_setting.receivers_emails or [user.email]
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipient_emails,
                html_message=html_message,
                fail_silently=False
            )
            
            logger.info(f"Test notification sent to {recipient_emails}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending test notification: {str(e)}")
            return False
