from rest_framework import serializers
from .models import AreaOfInterest

class AreaOfInterestSerializer(serializers.ModelSerializer):
    geometry_type = serializers.SerializerMethodField()

    class Meta:
        model = AreaOfInterest
        exclude = ['geometry']  # atau tulis `fields = [...]` kalau mau eksplisit

    def get_geometry_type(self, obj):
        return obj.geometry_type
