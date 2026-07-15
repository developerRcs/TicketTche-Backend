import uuid

from django.db import models

from apps.companies.models import Company


class Withdrawal(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Aguardando aprovação"
        APPROVED = "approved", "Aprovado — aguardando envio"
        PROCESSING = "processing", "Processando"
        COMPLETED = "completed", "Concluído"
        FAILED = "failed", "Falhou"
        REJECTED = "rejected", "Rejeitado"

    # Statuses that keep the amount reserved against the company balance.
    # FAILED/REJECTED release the funds back to available_balance.
    RESERVING_STATUSES = ("pending", "approved", "processing", "completed")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="withdrawals")
    requested_by = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.SET_NULL,
        null=True,
        related_name="withdrawal_requests",
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    pix_key = models.CharField(max_length=255)
    pix_key_type = models.CharField(
        max_length=20,
        choices=[
            ("cpf", "CPF"),
            ("cnpj", "CNPJ"),
            ("email", "E-mail"),
            ("phone", "Telefone"),
            ("random", "Chave aleatória"),
        ],
    )

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    mp_transfer_id = models.CharField(max_length=255, blank=True)
    failure_reason = models.TextField(blank=True)

    reviewed_by = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="withdrawals_reviewed",
        help_text="Admin da plataforma que aprovou/rejeitou o saque.",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.company.name} — R${self.amount} ({self.get_status_display()})"
