import pytest

from apps.accounts.tests.factories import UserFactory
from apps.audit.models import AuditLog


@pytest.mark.django_db
class TestAuditLog:
    def test_create_audit_log(self):
        user = UserFactory()
        log = AuditLog.objects.create(
            action="test_action",
            actor=user,
            target_type="User",
            target_id=str(user.pk),
            target_repr=str(user),
        )
        assert log.pk is not None
        assert log.action == "test_action"
        assert log.actor == user

    def test_audit_log_str(self):
        log = AuditLog.objects.create(action="test_action")
        assert "test_action" in str(log)

    def test_audit_log_null_actor(self):
        log = AuditLog.objects.create(action="system_action", actor=None)
        assert log.actor is None

    def test_uuid_primary_key(self):
        import uuid
        log = AuditLog.objects.create(action="test_action")
        assert isinstance(log.pk, uuid.UUID)
