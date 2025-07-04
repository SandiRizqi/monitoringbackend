# data/urls.py
from django.urls import path
from .views import (
    UserAOIListView, UserAreaOfInterestTileView, UserDeforestationTileView, 
    UserHotspotAlertTileView, HotspotAlertAPIView, DeforestationAlertDetailView,
    hotspot_chart_data, company_table_data, event_list_data, hotspot_stats_data,
    deforestation_chart_data, deforestation_company_table_data, 
    deforestation_event_list_data, deforestation_stats_data,
    DeforestationVerificationAPIView, HotspotVerificationAPIView
)

urlpatterns = [
    path('user-aois/', UserAOIListView.as_view(), name='user-aois'),
    path('hotspot-alerts/', HotspotAlertAPIView.as_view(), name='hotspotalert-list'),
    path('hotspot-alerts/<int:pk>/', HotspotAlertAPIView.as_view(), name='hotspotalert-detail'),

     path('deforestation-alerts/<str:id>/', DeforestationAlertDetailView.as_view(), name='deforestation-alert-detail'),
    
    # Tiles
    path('tiles/user-aois/<int:z>/<int:x>/<int:y>/', UserAreaOfInterestTileView.as_view(), name='user-aois-tile'),
    path('tiles/deforestation/<int:z>/<int:x>/<int:y>/', UserDeforestationTileView.as_view(), name='deforestation-tile'),
    path('tiles/hotspotalert/<int:z>/<int:x>/<int:y>/', UserHotspotAlertTileView.as_view(), name='hotspotalert-tile'),

    # Chart dan Stats APIs
    path('hotspot-chart/', hotspot_chart_data, name='hotspot-chart'),
    path('company-table/', company_table_data, name='company-table'),
    path('event-list/', event_list_data, name='event-list'),
    path('hotspot-stats/', hotspot_stats_data, name='hotspot-stats'),

    path('deforestation-chart/', deforestation_chart_data, name='deforestation-chart'),
    path('deforestation-company-table/', deforestation_company_table_data, name='deforestation-company-table'),
    path('deforestation-event-list/', deforestation_event_list_data, name='deforestation-event-list'),
    path('deforestation-stats/', deforestation_stats_data, name='deforestation-stats'),

    path('deforestation-verifications/', DeforestationVerificationAPIView.as_view(), name='deforestation-verification-list'),
    path('deforestation-verifications/<int:pk>/', DeforestationVerificationAPIView.as_view(), name='deforestation-verification-detail'),

    path('hotspot-verifications/', HotspotVerificationAPIView.as_view(), name='hotspot-verification-list'),
    path('hotspot-verifications/<int:pk>/', HotspotVerificationAPIView.as_view(), name='hotspot-verification-detail'),
]
