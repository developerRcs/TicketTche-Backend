# Generated migration for TicketTransfer new fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="tickettransfer",
            name="confirmation_code",
            field=models.CharField(blank=True, max_length=6),
        ),
        migrations.AddField(
            model_name="tickettransfer",
            name="owner_confirmed",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="tickettransfer",
            name="agreed_price",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Agreed transfer price. Must be within ±10% of original ticket price.",
                max_digits=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="tickettransfer",
            name="payment_confirmed",
            field=models.BooleanField(
                default=False,
                help_text="Set to True once receiver confirms payment was made.",
            ),
        ),
    ]
