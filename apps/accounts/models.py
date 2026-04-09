import uuid

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.core.image_optimizer import optimize_image
from apps.core.validators import ImageFileValidator, validate_cpf

from .managers import CustomUserManager


class CustomUser(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        SUPER_ADMIN = "super_admin", "Super Admin"
        ADMIN = "admin", "Admin"
        ORGANIZER = "organizer", "Organizer"
        CUSTOMER = "customer", "Customer"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    cpf = models.CharField(
        max_length=14,
        unique=True,
        validators=[validate_cpf],
        verbose_name="CPF",
        help_text="CPF no formato 000.000.000-00",
        null=True,
        blank=True,
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True, validators=[ImageFileValidator()])
    date_joined = models.DateTimeField(default=timezone.now)

    objects = CustomUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def save(self, *args, **kwargs):
        if self.avatar and self._state.adding or (
            self.pk and self.__class__.objects.filter(pk=self.pk).exclude(avatar=self.avatar.name if self.avatar else "").exists()
        ):
            optimize_image(self.avatar, "avatar")
        super().save(*args, **kwargs)
