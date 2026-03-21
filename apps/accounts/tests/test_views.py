import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from .factories import SuperAdminFactory, UserFactory


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    u = UserFactory()
    u.set_password("testpass123!")
    u.save()
    return u


@pytest.fixture
def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestLoginView:
    def test_login_success(self, api_client, user):
        url = reverse("token_obtain_pair")
        response = api_client.post(url, {"email": user.email, "password": "testpass123!"})
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh_token" in response.cookies

    def test_login_invalid_credentials(self, api_client, user):
        url = reverse("token_obtain_pair")
        response = api_client.post(url, {"email": user.email, "password": "wrongpass"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_nonexistent_user(self, api_client):
        url = reverse("token_obtain_pair")
        response = api_client.post(url, {"email": "nobody@example.com", "password": "pass"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestRegisterView:
    def test_register_success(self, api_client):
        url = reverse("register")
        data = {
            "email": "new@example.com",
            "first_name": "New",
            "last_name": "User",
            "password": "securepass123!",
            "password_confirm": "securepass123!",
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["email"] == "new@example.com"

    def test_register_password_mismatch(self, api_client):
        url = reverse("register")
        data = {
            "email": "new2@example.com",
            "first_name": "New",
            "last_name": "User",
            "password": "securepass123!",
            "password_confirm": "different123!",
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_duplicate_email(self, api_client, user):
        url = reverse("register")
        data = {
            "email": user.email,
            "first_name": "New",
            "last_name": "User",
            "password": "securepass123!",
            "password_confirm": "securepass123!",
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestTokenRefreshView:
    def test_refresh_with_valid_cookie(self, api_client, user):
        login_url = reverse("token_obtain_pair")
        login_response = api_client.post(
            login_url, {"email": user.email, "password": "testpass123!"}
        )
        refresh_token = login_response.cookies.get("refresh_token").value

        refresh_url = reverse("token_refresh")
        api_client.cookies["refresh_token"] = refresh_token
        response = api_client.post(refresh_url)
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data

    def test_refresh_without_cookie(self, api_client):
        refresh_url = reverse("token_refresh")
        response = api_client.post(refresh_url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestLogoutView:
    def test_logout_success(self, auth_client, user):
        # First login to get cookie
        login_url = reverse("token_obtain_pair")
        login_client = APIClient()
        login_response = login_client.post(
            login_url, {"email": user.email, "password": "testpass123!"}
        )
        refresh_token = login_response.cookies.get("refresh_token").value
        auth_client.cookies["refresh_token"] = refresh_token

        url = reverse("logout")
        response = auth_client.post(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_logout_unauthenticated(self, api_client):
        url = reverse("logout")
        response = api_client.post(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestMeView:
    def test_me_authenticated(self, auth_client, user):
        url = reverse("me")
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == user.email

    def test_me_unauthenticated(self, api_client):
        url = reverse("me")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestChangePasswordView:
    def test_change_password_success(self, auth_client, user):
        user.set_password("oldpass123!")
        user.save()
        url = reverse("change_password")
        data = {
            "old_password": "oldpass123!",
            "new_password": "newpass456!",
            "new_password_confirm": "newpass456!",
        }
        response = auth_client.post(url, data)
        assert response.status_code == status.HTTP_200_OK

    def test_change_password_wrong_old(self, auth_client, user):
        url = reverse("change_password")
        data = {
            "old_password": "wrongpass",
            "new_password": "newpass456!",
            "new_password_confirm": "newpass456!",
        }
        response = auth_client.post(url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_change_password_mismatch(self, auth_client):
        url = reverse("change_password")
        data = {
            "old_password": "testpass123!",
            "new_password": "newpass456!",
            "new_password_confirm": "different456!",
        }
        response = auth_client.post(url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestAccountsPermissions:
    def test_is_admin_or_super_admin(self):
        from apps.accounts.permissions import IsAdminOrSuperAdmin, IsSuperAdmin
        from rest_framework.test import APIRequestFactory
        factory = APIRequestFactory()

        # Test IsAdminOrSuperAdmin with admin user
        from apps.accounts.tests.factories import AdminUserFactory, SuperAdminFactory
        admin = AdminUserFactory()
        request = factory.get("/")
        request.user = admin
        perm = IsAdminOrSuperAdmin()
        assert perm.has_permission(request, None) is True

        # Test with regular user
        regular = UserFactory()
        request.user = regular
        assert perm.has_permission(request, None) is False

        # Test IsSuperAdmin with super admin
        super_admin = SuperAdminFactory()
        request.user = super_admin
        perm2 = IsSuperAdmin()
        assert perm2.has_permission(request, None) is True

        # Test IsSuperAdmin fails with admin
        request.user = admin
        assert perm2.has_permission(request, None) is False


@pytest.mark.django_db
class TestManagerValidations:
    def test_create_superuser_not_staff_raises(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        with pytest.raises(ValueError):
            User.objects.create_superuser(
                email="super2@example.com",
                password="pass123",
                first_name="Super",
                last_name="Admin",
                is_staff=False,
            )

    def test_create_superuser_not_superuser_raises(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        with pytest.raises(ValueError):
            User.objects.create_superuser(
                email="super3@example.com",
                password="pass123",
                first_name="Super",
                last_name="Admin",
                is_superuser=False,
            )


@pytest.mark.django_db
class TestLoginViewThrottling:
    def test_login_inactive_user(self, api_client):
        from django.core.cache import cache
        cache.clear()
        from apps.accounts.tests.factories import UserFactory
        user = UserFactory(is_active=False)
        user.set_password("testpass123!")
        user.save()
        from django.urls import reverse
        url = reverse("token_obtain_pair")
        response = api_client.post(url, {"email": user.email, "password": "testpass123!"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestTokenRefreshInvalidToken:
    def test_refresh_with_invalid_cookie(self, api_client):
        from django.urls import reverse
        refresh_url = reverse("token_refresh")
        api_client.cookies["refresh_token"] = "this-is-not-a-valid-jwt-token"
        response = api_client.post(refresh_url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestLogoutWithInvalidToken:
    def test_logout_with_invalid_refresh_token(self):
        from django.urls import reverse
        from apps.accounts.tests.factories import UserFactory
        user = UserFactory()
        client = APIClient()
        client.force_authenticate(user=user)
        client.cookies["refresh_token"] = "invalid-token"
        url = reverse("logout")
        response = client.post(url)
        # Should still succeed even with invalid refresh token
        assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
class TestLoginTokenErrorBranch:
    """Covers line 25: except TokenError -> raise InvalidToken."""

    def test_login_raises_invalid_token_on_token_error(self, api_client):
        from unittest.mock import patch
        from rest_framework_simplejwt.exceptions import TokenError
        from django.urls import reverse

        url = reverse("token_obtain_pair")

        with patch(
            "apps.accounts.views.TokenObtainPairView.get_serializer"
        ) as mock_get_ser:
            mock_ser = mock_get_ser.return_value
            mock_ser.is_valid.side_effect = TokenError("token error triggered")
            response = api_client.post(url, {"email": "x@x.com", "password": "wrong"})

        assert response.status_code == 401
