import pytest
from rest_framework import serializers

from apps.accounts.services import change_password, register_user, update_user

from .factories import UserFactory


@pytest.mark.django_db
class TestRegisterUser:
    def test_register_user_success(self):
        user = register_user(
            email="new@example.com",
            first_name="New",
            last_name="User",
            password="securepass123!",
        )
        assert user.email == "new@example.com"
        assert user.check_password("securepass123!")

    def test_register_duplicate_email(self):
        UserFactory(email="dup@example.com")
        with pytest.raises(serializers.ValidationError):
            register_user(
                email="dup@example.com",
                first_name="Dup",
                last_name="User",
                password="pass123",
            )


@pytest.mark.django_db
class TestChangePassword:
    def test_change_password_success(self):
        user = UserFactory()
        user.set_password("oldpass123!")
        user.save()
        change_password(user, "oldpass123!", "newpass456!")
        user.refresh_from_db()
        assert user.check_password("newpass456!")

    def test_change_password_wrong_old(self):
        user = UserFactory()
        user.set_password("oldpass123!")
        user.save()
        with pytest.raises(serializers.ValidationError):
            change_password(user, "wrongpass", "newpass456!")


@pytest.mark.django_db
class TestUpdateUser:
    def test_update_user(self):
        user = UserFactory(first_name="Old")
        updated = update_user(user, first_name="New")
        updated.refresh_from_db()
        assert updated.first_name == "New"
