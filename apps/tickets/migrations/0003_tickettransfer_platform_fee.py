from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0002_tickettransfer_transfer_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="tickettransfer",
            name="platform_fee",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="8% platform fee on the agreed_price.",
                max_digits=10,
                null=True,
            ),
        ),
    ]
