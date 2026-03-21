import factory
from django.contrib.auth import get_user_model
from factory.django import DjangoModelFactory

User = get_user_model()


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    password = factory.PostGenerationMethodCall("set_password", "testpass123!")
    role = User.Role.CUSTOMER
    is_active = True


class AdminUserFactory(UserFactory):
    role = User.Role.ADMIN
    is_staff = True


class SuperAdminFactory(UserFactory):
    role = User.Role.SUPER_ADMIN
    is_staff = True
    is_superuser = True


class OrganizerFactory(UserFactory):
    role = User.Role.ORGANIZER
