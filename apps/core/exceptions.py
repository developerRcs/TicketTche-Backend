from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        error_data = {
            "error": str(exc),
            "code": getattr(exc, "default_code", "error"),
            "details": response.data,
        }
        response.data = error_data

    return response
