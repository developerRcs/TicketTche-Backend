from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="platform_fee",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                help_text="8% platform fee on the order subtotal.",
                max_digits=10,
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="grand_total",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                help_text="total + platform_fee (amount charged to buyer).",
                max_digits=12,
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="mp_order_id",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="order",
            name="mp_payment_id",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="order",
            name="pix_qr_code",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="order",
            name="pix_qr_code_base64",
            field=models.TextField(blank=True),
        ),
    ]
