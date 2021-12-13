# Generated by Django 2.2.24 on 2021-09-22 18:57

from django.db import migrations, models
import oscar.utils.models


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0052_add_scholarship_coupon_category'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='ancestors_are_public',
            field=models.BooleanField(db_index=True, default=True, help_text='The ancestors of this category are public', verbose_name='Ancestor categories are public'),
        ),
        migrations.AddField(
            model_name='category',
            name='is_public',
            field=models.BooleanField(db_index=True, default=True, help_text='Show this category in search results and catalogue listings.', verbose_name='Is public'),
        ),
        migrations.AddField(
            model_name='historicalcategory',
            name='ancestors_are_public',
            field=models.BooleanField(db_index=True, default=True, help_text='The ancestors of this category are public', verbose_name='Ancestor categories are public'),
        ),
        migrations.AddField(
            model_name='historicalcategory',
            name='is_public',
            field=models.BooleanField(db_index=True, default=True, help_text='Show this category in search results and catalogue listings.', verbose_name='Is public'),
        ),
        migrations.AlterField(
            model_name='historicalproduct',
            name='is_public',
            field=models.BooleanField(db_index=True, default=True, help_text='Show this product in search results and catalogue listings.', verbose_name='Is public'),
        ),
        migrations.AlterField(
            model_name='product',
            name='is_public',
            field=models.BooleanField(db_index=True, default=True, help_text='Show this product in search results and catalogue listings.', verbose_name='Is public'),
        ),
        migrations.AlterField(
            model_name='productattributevalue',
            name='value_file',
            field=models.FileField(blank=True, max_length=255, null=True, upload_to=oscar.utils.models.get_image_upload_path),
        ),
        migrations.AlterField(
            model_name='productattributevalue',
            name='value_image',
            field=models.ImageField(blank=True, max_length=255, null=True, upload_to=oscar.utils.models.get_image_upload_path),
        ),
        migrations.AlterField(
            model_name='productimage',
            name='original',
            field=models.ImageField(max_length=255, upload_to=oscar.utils.models.get_image_upload_path, verbose_name='Original'),
        ),
    ]