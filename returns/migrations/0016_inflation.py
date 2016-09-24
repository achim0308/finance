# -*- coding: utf-8 -*-
# Generated by Django 1.9.1 on 2016-05-16 08:23
from __future__ import unicode_literals

from django.db import migrations, models
import django_countries.fields


class Migration(migrations.Migration):

    dependencies = [
        ('returns', '0015_auto_20160514_1747'),
    ]

    operations = [
        migrations.CreateModel(
            name='Inflation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(verbose_name='Inflation date')),
                ('inflationIndex', models.DecimalField(decimal_places=2, max_digits=5, verbose_name='Inflation index')),
                ('country', django_countries.fields.CountryField(max_length=2)),
            ],
        ),
    ]