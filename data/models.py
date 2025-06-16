from django.contrib.gis.db import models
from django.utils import timezone
import uuid

class AreaOfInterest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    geometry = models.GeometryField()
    srid = models.IntegerField(default=4326)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    fill_color = models.CharField(
        max_length=9, blank=True, null=True,
        help_text="Hanya untuk Polygon, hex dengan alpha (cth: #00FF0044)"
    )
    stroke_color = models.CharField(
        max_length=7, blank=True, null=True,
        help_text="Untuk Polygon/Line/Point, hex tanpa alpha (cth: #333333)"
    )
    stroke_width = models.FloatField(
        default=1.0,
        help_text="Untuk LineString dan Point outline"
    )
    marker_size = models.FloatField(
        default=1.0,
        help_text="Untuk Point (diameter marker)"
    )

  

    class Meta:
        verbose_name = "Area of Interest"
        verbose_name_plural = "Areas of Interest"
        # permissions = [
        #         ("delete_areaofinterest", "Can delete area of interest"),
        #         ("add_areaofinterest", "Can add area of interest"),
        #         ("change_areaofinterest", "Can change area of interest"),
        #         ]


    def __str__(self):
        return self.name

    @property
    def geometry_type(self):
        return self.geometry.geom_type if self.geometry else None
    
sources = (("LAPAN", "LAPAN"),
           ("SIPONGI", "SIPONGI"))

class Hotspots(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    key = models.CharField(max_length=255)
    source = models.CharField(max_length=255)
    radius = models.FloatField()
    long = models.FloatField()
    lat = models.FloatField()
    provinsi = models.CharField(max_length=255)
    kabupaten = models.CharField(max_length=255)
    kecamatan = models.CharField(max_length=255)
    date = models.DateField()
    times = models.TimeField()
    conf = models.IntegerField()
    sat = models.CharField(max_length=255)
    geom = models.PointField(srid=4326, geography=True, null=True, blank=True, editable=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.id} - {self.key}"
    

HOTSPOT_ALERT_CATEGORIES = (
    ("AMAN", "Aman"),
    ("PERHATIAN", "Perhatian"),
    ("WASPADA", "Waspada"),
    ("BAHAYA", "Bahaya"),
)

class HotspotAlert(models.Model):
    id = models.AutoField(primary_key=True)
    
    hotspot = models.ForeignKey(
        Hotspots, on_delete=models.CASCADE, related_name="alerts"
    )
    area_of_interest = models.ForeignKey(
        AreaOfInterest, on_delete=models.CASCADE, related_name="hotspot_alerts"
    )

    distance = models.FloatField(
        help_text="Jarak dari hotspot ke batas AOI (meter)", blank=True, null=True
    )

    category = models.CharField(
        max_length=10,
        choices=HOTSPOT_ALERT_CATEGORIES,
        default="AMAN"
    )

    alert_date = models.DateField(default=timezone.now)
    confidence = models.IntegerField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-alert_date']
        indexes = [
            models.Index(fields=['alert_date']),
            models.Index(fields=['category']),
            models.Index(fields=['hotspot']),
            models.Index(fields=['area_of_interest']),
        ]
        unique_together = ('hotspot', 'area_of_interest')

    def __str__(self):
        return f"{self.alert_date} - {self.area_of_interest.name} - {self.category}"
    
    
class DeforestationAlerts(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    company = models.ForeignKey(AreaOfInterest, on_delete=models.CASCADE, related_name='deforestation_alerts')
    event_id = models.CharField(max_length=250, unique=True)
    alert_date = models.DateField(default=timezone.now)
    created = models.DateField(auto_now_add=True)
    updated = models.DateField(auto_now=True)
    confidence = models.IntegerField(blank=True, null=True, default=0)
    area = models.DecimalField(max_digits=15, decimal_places=4, blank=True, null=True)
    geom = models.PolygonField(srid=4326, geography=True, null=True, blank=True)

    class Meta:
        ordering = ['-alert_date']
        indexes = [
            models.Index(fields=['alert_date']),
            models.Index(fields=['event_id']),
            models.Index(fields=['company']),
            models.Index(fields=['geom']),
        ]

    def __str__(self):
        return f"{self.company} - {self.alert_date} - {self.event_id}"