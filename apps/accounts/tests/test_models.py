import pytest
from django.contrib.auth import get_user_model

from .factories import SuperAdminFactory, UserFactory

User = get_user_model()


@pytest.mark.django_db
class TestCustomUser:
    def test_create_user(self):
        user = UserFactory()
        assert user.pk is not None
        assert user.is_active is True
        assert user.role == User.Role.CUSTOMER

    def test_full_name_property(self):
        user = UserFactory(first_name="John", last_name="Doe")
        assert user.full_name == "John Doe"

    def test_email_is_username_field(self):
        assert User.USERNAME_FIELD == "email"

    def test_required_fields(self):
        assert "first_name" in User.REQUIRED_FIELDS
        assert "last_name" in User.REQUIRED_FIELDS

    def test_role_choices(self):
        choices = [c[0] for c in User.Role.choices]
        assert "super_admin" in choices
        assert "admin" in choices
        assert "organizer" in choices
        assert "customer" in choices

    def test_uuid_primary_key(self):
        user = UserFactory()
        import uuid
        assert isinstance(user.pk, uuid.UUID)

    def test_email_uniqueness(self):
        from django.db import IntegrityError
        UserFactory(email="unique@example.com")
        with pytest.raises(Exception):
            UserFactory(email="unique@example.com")

    def test_str_returns_email(self):
        user = UserFactory(email="test@example.com")
        assert str(user) == "test@example.com"

    def test_create_superuser(self):
        user = User.objects.create_superuser(
            email="super@example.com",
            password="pass123",
            first_name="Super",
            last_name="Admin",
        )
        assert user.is_superuser is True
        assert user.is_staff is True
        assert user.role == "super_admin"

    def test_create_user_no_email_raises(self):
        with pytest.raises(ValueError):
            User.objects.create_user(email="", password="pass123")
