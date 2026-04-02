import factory
from factory.django import DjangoModelFactory

from apps.accounts.tests.factories import UserFactory
from apps.companies.models import Company, CompanyMember


class CompanyFactory(DjangoModelFactory):
    class Meta:
        model = Company

    name = factory.Sequence(lambda n: f"Company {n}")
    owner = factory.SubFactory(UserFactory)
    description = factory.Faker("text")
    is_active = True


class CompanyMemberFactory(DjangoModelFactory):
    class Meta:
        model = CompanyMember

    user = factory.SubFactory(UserFactory)
    company = factory.SubFactory(CompanyFactory)
    role = CompanyMember.Role.STAFF
