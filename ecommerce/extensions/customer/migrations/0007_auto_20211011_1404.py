# Generated by Django 2.2.24 on 2021-10-11 14:04

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('order', '0025_auto_20211011_1404'),
        ('customer', '0006_auto_20200305_1448'),
    ]

    operations = [
        migrations.DeleteModel(
            name='CommunicationEventType',
        ),
        migrations.RemoveField(
            model_name='notification',
            name='recipient',
        ),
        migrations.RemoveField(
            model_name='notification',
            name='sender',
        ),
        migrations.DeleteModel(
            name='Email',
        ),
        migrations.DeleteModel(
            name='Notification',
        ),
    ]