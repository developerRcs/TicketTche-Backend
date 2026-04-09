import hashlib
import hmac
import io
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string

from apps.core.image_optimizer import optimize_image


class Ticket(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        USED = "used", "Used"
        CANCELLED = "cancelled", "Cancelled"
        TRANSFERRED = "transferred", "Transferred"
        PENDING_TRANSFER = "pending_transfer", "Pending Transfer"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        "events.Event", on_delete=models.CASCADE, related_name="tickets"
    )
    ticket_type = models.ForeignKey(
        "events.TicketType", on_delete=models.CASCADE, related_name="tickets"
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tickets"
    )
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tickets",
    )
    qr_code = models.ImageField(upload_to="qrcodes/", blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    checked_in_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Ticket {self.id} - {self.owner.email}"

    def generate_qr_code(self):
        import qrcode
        signing_key = settings.QR_SIGNING_KEY.encode()
        signature = hmac.new(
            signing_key, str(self.id).encode(), hashlib.sha256
        ).hexdigest()[:16]
        data = f"{self.id}:{signature}"
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        filename = f"ticket_{self.id}.png"
        self.qr_code.save(filename, ContentFile(buffer.read()), save=False)
        # Otimizar o PNG gerado (420×420, sem exif, compressão máxima)
        optimize_image(self.qr_code, "qr_code")

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        if is_new and not self.qr_code:
            super().save(*args, **kwargs)
            self.generate_qr_code()
            kwargs.pop("force_insert", None)
            super().save(update_fields=["qr_code"])
        else:
            super().save(*args, **kwargs)


class TicketTransfer(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="transfers")
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_transfers"
    )
    to_email = models.EmailField()
    token = models.CharField(max_length=64, unique=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    confirmation_code = models.CharField(max_length=6, blank=True)
    owner_confirmed = models.BooleanField(default=False)
    agreed_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Agreed transfer price. Must be within ±10% of original ticket price.",
    )
    platform_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="8% platform fee on the agreed_price. Total receiver pays = agreed_price + platform_fee.",
    )
    payment_confirmed = models.BooleanField(
        default=False,
        help_text="Set to True once receiver confirms payment was made.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def __str__(self):
        return f"Transfer {self.id} from {self.from_user.email} to {self.to_email}"

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = get_random_string(64)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=48)
        if not self.confirmation_code:
            import random
            self.confirmation_code = str(random.randint(100000, 999999))
        super().save(*args, **kwargs)
