# accounts/models.py
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from data.models import AreaOfInterest
from django.db import models



class CustomUserManager(BaseUserManager):
    def create_user(self, email, name=None, picture=None, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, name=name, picture=picture, **extra_fields)
        user.set_unusable_password()  # karena user login dari Google
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        user = self.create_user(email=email, password=password, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

class Users(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=255, blank=True, null=True)
    picture = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    areas_of_interest = models.ManyToManyField(AreaOfInterest, blank=True, related_name="users_aoi")


    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def __str__(self):
        return self.email




class AccountNotificationSetting(models.Model):
    user = models.OneToOneField(Users, on_delete=models.CASCADE, related_name='notification_setting')

    # Jenis pengiriman notifikasi
    email_notifications = models.BooleanField(default=True)
    # sms_notifications = models.BooleanField(default=False)
    push_notifications = models.BooleanField(default=True)

    # Preferensi notifikasi konten
    # notify_on_new_message = models.BooleanField(default=True)
    # notify_on_system_alert = models.BooleanField(default=True)
    # notify_on_activity = models.BooleanField(default=False)

    # 🔥 Tambahan untuk monitoring
    notify_on_new_hotspot_data = models.BooleanField(default=True)
    notify_on_new_deforestation_data = models.BooleanField(default=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Notification settings for {self.user.email}"
