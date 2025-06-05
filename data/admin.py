from django.contrib import admin
from django.contrib.gis.forms import OSMWidget
from django import forms
from .models import AreaOfInterest

class AreaOfInterestForm(forms.ModelForm):
    class Meta:
        model = AreaOfInterest
        fields = '__all__'
        widgets = {
            'geometry': OSMWidget(attrs={'map_width': 800, 'map_height': 500}),
        }

@admin.register(AreaOfInterest)
class AreaOfInterestAdmin(admin.ModelAdmin):
    form = AreaOfInterestForm
    list_display = ("name", "geometry_type", "created_at")
    search_fields = ("name", "description")
