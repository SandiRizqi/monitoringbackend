from rest_framework import serializers
from .models import AreaOfInterest

class AreaOfInterestSerializer(serializers.ModelSerializer):
    geometry_type = serializers.SerializerMethodField()
    geometry = serializers.SerializerMethodField()

    class Meta:
        model = AreaOfInterest
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

