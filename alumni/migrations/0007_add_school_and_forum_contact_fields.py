from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("alumni", "0006_alter_schooljoinrequest_unique_together_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="school",
            name="main_contact_number",
            field=models.CharField(blank=True, default="", max_length=20),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="independentforumrequest",
            name="contact_name",
            field=models.CharField(blank=True, default="", max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="independentforumrequest",
            name="contact_email",
            field=models.EmailField(blank=True, default="", max_length=254),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="independentforumrequest",
            name="contact_phone",
            field=models.CharField(blank=True, default="", max_length=20),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="independentforumrequest",
            name="objectives",
            field=models.TextField(blank=True, default=""),
            preserve_default=False,
        ),
    ]
