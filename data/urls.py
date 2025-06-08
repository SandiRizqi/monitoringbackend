from django.urls import path
from .views import UserAOIListView, UserAreaOfInterestTileView

urlpatterns = [
    path('user-aois/', UserAOIListView.as_view(), name='user-aois'),
    path('tiles/user-aois/<int:z>/<int:x>/<int:y>/', UserAreaOfInterestTileView.as_view(), name='user-aois-tile'),
]
