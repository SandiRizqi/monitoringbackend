# urls.py
from django.urls import path
from .views import login_view, user_info_view, save_google_user

urlpatterns = [
    path('login/', login_view, name='login'),
    path('saveuser/', save_google_user, name='save_google_user'),
    path('user-info/', user_info_view, name='user-info'),
]
