from django.urls import path
from .views import (
    UserAOIListView, UserAreaOfInterestTileView, UserDeforestationTileView, 
    UserHotspotAlertTileView, HotspotAlertAPIView,
    hotspot_chart_data, company_table_data, event_list_data, hotspot_stats_data
)

urlpatterns = [
    path('user-aois/', UserAOIListView.as_view(), name='user-aois'),
    path('hotspot-alerts/', HotspotAlertAPIView.as_view(), name='hotspotalert-list'),
    path('hotspot-alerts/<int:pk>/', HotspotAlertAPIView.as_view(), name='hotspotalert-detail'),
    
    # Tiles
    path('tiles/user-aois/<int:z>/<int:x>/<int:y>/', UserAreaOfInterestTileView.as_view(), name='user-aois-tile'),
    path('tiles/deforestation/<int:z>/<int:x>/<int:y>/', UserDeforestationTileView.as_view(), name='deforestation-tile'),
    path('tiles/hotspotalert/<int:z>/<int:x>/<int:y>/', UserHotspotAlertTileView.as_view(), name='hotspotalert-tile'),

    # Chart dan Stats APIs
    path('hotspot-chart/', hotspot_chart_data, name='hotspot-chart'),
    path('company-table/', company_table_data, name='company-table'),
    path('event-list/', event_list_data, name='event-list'),
    path('hotspot-stats/', hotspot_stats_data, name='hotspot-stats'),
]
