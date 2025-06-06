from rest_framework import serializers
from .models import AreaOfInterest

class AreaOfInterestSerializer(serializers.ModelSerializer):
    geometry_type = serializers.SerializerMethodField()
    geometry = serializers.SerializerMethodField()

    class Meta:
        model = AreaOfInterest
        exclude = ['geometry']  # akan dikendalikan manual oleh get_geometry

    def get_geometry_type(self, obj):
        return obj.geometry_type

    def get_geometry(self, obj):
        request = self.context.get('request')
        include_geom = False
        if request:
            include_geom = request.query_params.get('geom') == 'true'
        return obj.geometry.geojson if include_geom else None

