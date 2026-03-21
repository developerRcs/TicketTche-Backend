import uuid

from django.conf import settings
from django.db import models
from django.utils.crypto import get_random_string
from django.utils.text import slugify


class Event(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField()
    slug = models.SlugField(unique=True, max_length=300, blank=True)
    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="events",
    )
    location = models.CharField(max_length=255)
    location_url = models.URLField(blank=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    cover_image = models.ImageField(upload_to="events/", null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    is_online = models.BooleanField(default=False)
    capacity = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            suffix = get_random_string(6).lower()
            slug = f"{base_slug}-{suffix}"
            while Event.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                suffix = get_random_string(6).lower()
                slug = f"{base_slug}-{suffix}"
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def tickets_sold(self):
        return sum(tt.quantity_sold for tt in self.ticket_types.all())


class TicketType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="ticket_types")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    quantity_sold = models.PositiveIntegerField(default=0)
    sale_start = models.DateTimeField(null=True, blank=True)
    sale_end = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} - {self.event.title}"

    @property
    def quantity_available(self):
        return self.quantity - self.quantity_sold
