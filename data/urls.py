from django.urls import path
from .views import UserAOIListView, UserAreaOfInterestTileView, UserDeforestationTileView, UserHotspotAlertTileView, HotspotAlertAPIView

urlpatterns = [
    path('user-aois/', UserAOIListView.as_view(), name='user-aois'),
    path('hotspot-alerts/', HotspotAlertAPIView.as_view(), name='hotspotalert-list'),
    path('hotspot-alerts/<int:pk>/', HotspotAlertAPIView.as_view(), name='hotspotalert-detail'),

    path('tiles/user-aois/<int:z>/<int:x>/<int:y>/', UserAreaOfInterestTileView.as_view(), name='user-aois-tile'),
    path('tiles/deforestation/<int:z>/<int:x>/<int:y>/', UserDeforestationTileView.as_view(), name='deforestation-tile'),
    path('tiles/hotspotalert/<int:z>/<int:x>/<int:y>/', UserHotspotAlertTileView.as_view(), name='hotspotalert-tile'),
]
