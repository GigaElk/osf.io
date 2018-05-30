# -*- coding: utf-8 -*-
# Generated by Django 1.11.11 on 2018-05-14 22:15
from __future__ import unicode_literals

from django.db import migrations, models
import osf.models.spam
import osf.utils.datetime_aware_jsonfield
import osf.utils.fields


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0100_notificationdigest_provider'),
    ]

    operations = [
        migrations.AddField(
            model_name='preprintservice',
            name='date_last_reported',
            field=osf.utils.fields.NonNaiveDateTimeField(blank=True, db_index=True, default=None, null=True),
        ),
        migrations.AddField(
            model_name='preprintservice',
            name='reports',
            field=osf.utils.datetime_aware_jsonfield.DateTimeAwareJSONField(blank=True, default=dict, encoder=osf.utils.datetime_aware_jsonfield.DateTimeAwareJSONEncoder, validators=[osf.models.spam._validate_reports]),
        ),
        migrations.AddField(
            model_name='preprintservice',
            name='spam_data',
            field=osf.utils.datetime_aware_jsonfield.DateTimeAwareJSONField(blank=True, default=dict, encoder=osf.utils.datetime_aware_jsonfield.DateTimeAwareJSONEncoder),
        ),
        migrations.AddField(
            model_name='preprintservice',
            name='spam_pro_tip',
            field=models.CharField(blank=True, default=None, max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='preprintservice',
            name='spam_status',
            field=models.IntegerField(blank=True, db_index=True, default=None, null=True),
        ),
    ]