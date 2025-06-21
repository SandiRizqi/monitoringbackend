# accounts/serializers.py
from rest_framework import serializers
from .models import AccountNotificationSetting

class AccountNotificationSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountNotificationSetting
        fields = "__all__"
        read_only_fields = ("user", "updated_at")
