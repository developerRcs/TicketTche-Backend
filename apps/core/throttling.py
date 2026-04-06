from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    rate = "5/min"
    scope = "login"


class RegisterRateThrottle(AnonRateThrottle):
    rate = "10/hour"
    scope = "register"


class TokenRefreshRateThrottle(AnonRateThrottle):
    """Limit token refresh attempts to prevent brute-force on refresh cookie."""
    rate = "20/min"
    scope = "token_refresh"


class ChangePasswordRateThrottle(UserRateThrottle):
    """Limit password change attempts to prevent brute-force."""
    rate = "5/hour"
    scope = "change_password"


class PaymentRateThrottle(UserRateThrottle):
    """Limit payment attempts to prevent card testing / abuse."""
    rate = "10/hour"
    scope = "payment"


class CheckoutRateThrottle(UserRateThrottle):
    """Limit checkout creation to prevent order spam."""
    rate = "30/hour"
    scope = "checkout"


class PasswordResetRateThrottle(AnonRateThrottle):
    """Limit password reset requests to prevent email spam — 3/hour per IP."""
    rate = "3/hour"
    scope = "password_reset"
