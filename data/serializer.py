from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer
from .models import AreaOfInterest, HotspotAlert, DeforestationAlerts

class AreaOfInterestSerializer(serializers.ModelSerializer):
    geometry_type = serializers.SerializerMethodField()
    geometry = serializers.SerializerMethodField()

    class Meta:
        model = AreaOfInterest
        geo_field = "geometry"  # penting!
        fields = '__all__'

    def get_geometry_type(self, obj):
        return obj.geometry_type

    def get_geometry(self, obj):
        request = self.context.get('request')
        if request and request.query_params.get('geom') == 'true':
            return obj.geometry.geojson  # pastikan ini GeoDjango GEOSGeometry
        return None
    
    def to_representation(self, instance):
        rep = super().to_representation(instance)
        request = self.context.get('request')
        if request and request.query_params.get('geom') != 'true':
            rep.pop('geometry', None)
        return rep



class AreaOfInterestGeoSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = AreaOfInterest
        geo_field = "geometry"   # nama field geometry di model kamu
        fields = '__all__'




class HotspotAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = HotspotAlert
        fields = '__all__'

class HotspotAlertGeoSerializer(serializers.ModelSerializer):
    hotspot_geom = serializers.SerializerMethodField()

    class Meta:
        model = HotspotAlert
        fields = '__all__'

    def get_hotspot_geom(self, obj):
        return obj.hotspot.geom.geojson if obj.hotspot and obj.hotspot.geom else None


class DeforestationAlertsSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = DeforestationAlerts
        geo_field = 'geom'
        fields = '__all__'