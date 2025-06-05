# urls.py
from django.urls import path
from .views import login_view, user_info_view

urlpatterns = [
    path('login/', login_view, name='login'),
    path('user-info/', user_info_view, name='user-info'),
]
