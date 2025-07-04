from django.contrib import admin
from django import forms
from .models import AreaOfInterest, Hotspots, DeforestationAlerts, HotspotAlert, HotspotVerification, DeforestationVerification

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
    list_filter = ('provinsi', 'kabupaten', 'date', 'sat')

class HotspotAlertAdmin(admin.ModelAdmin):
    list_display = ("hotspot", "area_of_interest", "category", "distance", "confidence", "alert_date")
    list_filter = ("category", "alert_date", "area_of_interest")
    search_fields = ("hotspot__id", "area_of_interest__name")
    ordering = ("-alert_date",)

class DeforestationAlertAdmin(admin.ModelAdmin):
    list_display = ('event_id', 'company', 'alert_date', 'confidence', 'area', 'created', 'updated')
    list_filter = ('company', 'alert_date')
    search_fields = ('event_id', 'company__name')
    ordering = ('-alert_date',)
    readonly_fields = ('created', 'updated')

    # Optional: Mengatur fieldset
    fieldsets = (
        (None, {
            'fields': ('event_id', 'company', 'alert_date', 'confidence', 'area', 'geom')
        }),
        ('Timestamps', {
            'fields': ('created', 'updated'),
            'classes': ('collapse',),
        }),
    )

class HotspotVerificationAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'hotspot',
        'verifier',
        'verification_date',
        'status',
        'fire_evidence',
        'created_at'
    )
    list_filter = ('status', 'fire_evidence', 'verification_date')
    search_fields = ('verifier__email', 'hotspot__id', 'description')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        (None, {
            'fields': (
                'hotspot',
                'verifier',
                'verification_date',
                'status',
                'fire_evidence',
                'description',
                'photo_urls',
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


class DeforestationVerificationAdmin(admin.ModelAdmin):
    list_display = ('alert', 'verification_date', 'status', 'area_ha', 'verifier')
    list_filter = ('status', 'verification_date')
    search_fields = ('alert__event_id', 'description', 'notes')


admin.site.register(AreaOfInterest, AreaOfInterestAdmin)
admin.site.register(Hotspots, HotspotsAdmin)
admin.site.register(HotspotAlert, HotspotAlertAdmin)
admin.site.register(HotspotVerification, HotspotVerificationAdmin)


admin.site.register(DeforestationAlerts, DeforestationAlertAdmin)
admin.site.register(DeforestationVerification, DeforestationVerificationAdmin)