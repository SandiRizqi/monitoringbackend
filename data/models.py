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
        default=1.5,
        help_text="Untuk LineString dan Point outline"
    )
    marker_size = models.FloatField(
        default=6.0,
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
