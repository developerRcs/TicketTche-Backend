# Generated manually on 2026-04-09

import apps.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_customuser_cpf"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="cnpj",
            field=models.CharField(
                blank=True,
                help_text="CNPJ no formato 00.000.000/0000-00",
                max_length=18,
                null=True,
                unique=True,
                validators=[apps.core.validators.validate_cnpj],
                verbose_name="CNPJ",
            ),
        ),
    ]
