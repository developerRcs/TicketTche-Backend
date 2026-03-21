from .middleware import get_current_request


def log_action(action, actor=None, target=None, metadata=None, request=None):
    from .models import AuditLog

    if request is None:
        request = get_current_request()

    ip_address = None
    user_agent = ""

    if request:
        ip_address = get_client_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "")

    target_type = ""
    target_id = ""
    target_repr = ""

    if target is not None:
        target_type = target.__class__.__name__
        target_id = str(getattr(target, "pk", ""))
        target_repr = str(target)

    AuditLog.objects.create(
        action=action,
        actor=actor if actor and getattr(actor, "is_authenticated", False) else None,
        target_type=target_type,
        target_id=target_id,
        target_repr=target_repr,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata=metadata or {},
    )


def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip
