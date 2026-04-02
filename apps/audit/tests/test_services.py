import pytest

from apps.accounts.tests.factories import UserFactory
from apps.audit.models import AuditLog
from apps.audit.services import log_action


@pytest.mark.django_db
class TestLogAction:
    def test_log_action_basic(self):
        user = UserFactory()
        log_action(action="test_action", actor=user, target=user)
        assert AuditLog.objects.filter(action="test_action").exists()

    def test_log_action_with_metadata(self):
        user = UserFactory()
        log_action(
            action="test_action",
            actor=user,
            target=user,
            metadata={"key": "value"},
        )
        log = AuditLog.objects.get(action="test_action")
        assert log.metadata == {"key": "value"}

    def test_log_action_null_actor(self):
        log_action(action="system_action")
        assert AuditLog.objects.filter(action="system_action", actor=None).exists()

    def test_log_action_with_request(self, rf):
        user = UserFactory()
        request = rf.get("/")
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        request.META["HTTP_USER_AGENT"] = "TestAgent/1.0"
        log_action(action="test_action", actor=user, target=user, request=request)
        log = AuditLog.objects.get(action="test_action")
        assert log.ip_address == "127.0.0.1"
        assert log.user_agent == "TestAgent/1.0"


@pytest.mark.django_db
class TestGetClientIp:
    def test_get_ip_from_x_forwarded_for(self, rf):
        from apps.audit.services import get_client_ip
        request = rf.get("/")
        request.META["HTTP_X_FORWARDED_FOR"] = "203.0.113.1, 10.0.0.1"
        ip = get_client_ip(request)
        assert ip == "203.0.113.1"

    def test_get_ip_from_remote_addr(self, rf):
        from apps.audit.services import get_client_ip
        request = rf.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        ip = get_client_ip(request)
        assert ip == "192.168.1.1"
