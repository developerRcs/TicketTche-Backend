from django.conf import settings
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        # In production never expose raw exception string — it can leak internal details
        error_message = str(exc) if settings.DEBUG else _safe_error_message(exc)
        error_data = {
            "error": error_message,
            "code": getattr(exc, "default_code", "error"),
            "details": response.data,
        }
        response.data = error_data

    return response


def _safe_error_message(exc) -> str:
    """Return a safe, generic message for production. Only DRF known exceptions get their message."""
    from rest_framework.exceptions import APIException
    if isinstance(exc, APIException):
        return exc.detail if isinstance(exc.detail, str) else "Request error."
    return "An unexpected error occurred."
