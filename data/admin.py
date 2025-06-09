from django.contrib import admin
from django import forms
from django.utils.safestring import mark_safe
from .models import AreaOfInterest, Hotspots

class ColorAlphaWidget(forms.TextInput):
    class Media:
        js = ('https://jscolor.com/releases/2.4.6/jscolor.js',)

    def __init__(self, attrs=None):
        default_attrs = {
            'class': 'jscolor',
            'data-jscolor': '{"alpha":1, "hash":true, "format":"hex"}'
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)

class AreaOfInterestForm(forms.ModelForm):
    class Meta:
        model = AreaOfInterest
        fields = '__all__'
        widgets = {
            'fill_color': ColorAlphaWidget(),
            'stroke_color': ColorAlphaWidget(),
        }

class AreaOfInterestAdmin(admin.ModelAdmin):
    form = AreaOfInterestForm
    list_display = ('name', 'geometry_type', 'fill_color', 'stroke_color')


class HotspotsAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'key', 'source', 'radius', 'long', 'lat',
        'provinsi', 'kabupaten', 'kecamatan', 'date',
        'times', 'conf', 'sat'
    )
    search_fields = ('id', 'key', 'source', 'provinsi', 'kabupaten', 'kecamatan')
    list_filter = ('provinsi', 'kabupaten', 'kecamatan', 'date', 'sat')

admin.site.register(AreaOfInterest, AreaOfInterestAdmin)
admin.site.register(Hotspots, HotspotsAdmin)
