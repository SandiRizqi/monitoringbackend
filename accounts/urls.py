# accounts/urls.py
from django.urls import path
from .views import login_view, user_info_view, save_google_user, AccountNotificationSettingView, send_test_notification, webhook_notification_receiver

urlpatterns = [
    path('login/', login_view, name='login'),
    path('saveuser/', save_google_user, name='save_google_user'),
    path('user-info/', user_info_view, name='user-info'),
    path("notification-setting/", AccountNotificationSettingView.as_view(), name="notification-setting"),
    path("test-notification/", send_test_notification, name="test-notification"),
    path("webhook/", webhook_notification_receiver, name="webhook-receiver"),
]
