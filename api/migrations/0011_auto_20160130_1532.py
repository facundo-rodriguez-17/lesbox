# -*- coding: utf-8 -*-
# Generated by Django 1.9.1 on 2016-01-30 15:32
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0010_track_played_time'),
    ]

    operations = [
        migrations.AlterField(
            model_name='track',
            name='played_time',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
