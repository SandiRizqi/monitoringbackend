# data/serializer.py
from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer
from .models import AreaOfInterest, HotspotAlert, DeforestationAlerts
from .models import DeforestationVerification, DeforestationAlerts
from .models import AreaOfInterest, HotspotAlert, HotspotVerification
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.measure import Area


class AreaOfInterestSerializer(serializers.ModelSerializer):
    geometry_type = serializers.SerializerMethodField()
    geometry = serializers.SerializerMethodField()

    class Meta:
        model = AreaOfInterest
        geo_field = "geometry"
        fields = '__all__'

    def get_geometry_type(self, obj):
        return obj.geometry_type

    def get_geometry(self, obj):
        request = self.context.get('request')
        if request and request.query_params.get('geom') == 'true':
            return obj.geometry.geojson
        return None

    def validate_geometry(self, value):
        """Validasi maksimum luas AOI"""
        if value:
            if isinstance(value, dict):
                geom = GEOSGeometry(str(value))
            else:
                geom = value
            
            geom_transformed = geom.transform(3857, clone=True) 

            area_sqm = geom_transformed.area
            
            area_hectares = area_sqm / 10000
            
            MAX_AREA_HECTARES = 10000  # 10,000 hektar
            
            if area_hectares > MAX_AREA_HECTARES:
                raise serializers.ValidationError(
                    f"Area of Interest too large. Maximum allowed area is {MAX_AREA_HECTARES:,.0f} hectares, "
                    f"but the uploaded area is {area_hectares:,.2f} hectares."
                )
        
        return value

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        request = self.context.get('request')
        if request and request.query_params.get('geom') != 'true':
            rep.pop('geometry', None)
        return rep



class AreaOfInterestGeoSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = AreaOfInterest
        geo_field = "geometry"
        fields = '__all__'

    def validate_geometry(self, value):
        """Validasi maksimum luas AOI untuk GeoSerializer"""
        if value:
            if isinstance(value, dict):
                geom = GEOSGeometry(str(value))
            else:
                geom = value
            
            geom_transformed = geom.transform(3857, clone=True)
            
            area_sqm = geom_transformed.area
            
            area_hectares = area_sqm / 10000
            
            MAX_AREA_HECTARES = 10000 
            
            if area_hectares > MAX_AREA_HECTARES:
                raise serializers.ValidationError(
                    f"Area of Interest too large. Maximum allowed area is {MAX_AREA_HECTARES:,.0f} hectares, "
                    f"but the uploaded area is {area_hectares:,.2f} hectares."
                )
        
        return value




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
    

class DeforestationVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeforestationVerification
        fields = [
            'id', 'alert', 'verification_date', 'status', 'area_ha', 
            'description', 'notes', 'photo_urls', 'verifier', 'created', 'updated'
        ]
        read_only_fields = ['id', 'verifier', 'created', 'updated']
    
    def create(self, validated_data):
        # Set verifier dari request user
        validated_data['verifier'] = self.context['request'].user
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        # Update verifier jika diperlukan
        validated_data['verifier'] = self.context['request'].user
        return super().update(instance, validated_data)

class DeforestationVerificationListSerializer(serializers.ModelSerializer):
    alert_event_id = serializers.CharField(source='alert.event_id', read_only=True)
    alert_date = serializers.DateField(source='alert.alert_date', read_only=True)
    company_name = serializers.CharField(source='alert.company.name', read_only=True)
    verifier_name = serializers.CharField(source='verifier.username', read_only=True)
    
    class Meta:
        model = DeforestationVerification
        fields = [
            'id', 'verification_date', 'status', 'area_ha', 'description', 
            'notes', 'alert_event_id', 'alert_date', 'company_name', 'verifier_name'
        ]


class HotspotVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = HotspotVerification
        fields = [
            'id', 'hotspot', 'verification_date', 'description', 'status',
            'fire_evidence', 'photo_urls', 'verifier', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'verifier', 'created_at', 'updated_at']

    def create(self, validated_data):
        # Set verifier dari request user
        validated_data['verifier'] = self.context['request'].user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Update verifier jika diperlukan
        validated_data['verifier'] = self.context['request'].user
        return super().update(instance, validated_data)

class HotspotVerificationListSerializer(serializers.ModelSerializer):
    hotspot_id = serializers.CharField(source='hotspot.id', read_only=True)
    hotspot_date = serializers.DateField(source='hotspot.date', read_only=True)
    hotspot_confidence = serializers.IntegerField(source='hotspot.conf', read_only=True)
    verifier_name = serializers.CharField(source='verifier.username', read_only=True)

    class Meta:
        model = HotspotVerification
        fields = [
            'id', 'verification_date', 'status', 'fire_evidence', 'description',
            'hotspot_id', 'hotspot_date', 'hotspot_confidence', 'verifier_name'
        ]
