from django.contrib import admin
from django.contrib.gis.admin import OSMGeoAdmin
from .models import AreaOfInterest

@admin.register(AreaOfInterest)
class AreaOfInterestAdmin(OSMGeoAdmin):
    list_display = ("name", "geometry_type", "created_at")
    search_fields = ("name", "description")
