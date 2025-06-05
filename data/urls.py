from django.urls import path
from .views import UserAOIListView

urlpatterns = [
    path('user-aois/', UserAOIListView.as_view(), name='user-aois'),
]
