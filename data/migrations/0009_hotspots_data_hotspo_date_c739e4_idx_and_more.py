# Generated by Django 5.2.2 on 2025-06-17 02:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('data', '0008_hotspotalert'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='hotspots',
            index=models.Index(fields=['date'], name='data_hotspo_date_c739e4_idx'),
        ),
        migrations.AddIndex(
            model_name='hotspots',
            index=models.Index(fields=['conf'], name='data_hotspo_conf_708404_idx'),
        ),
    ]
