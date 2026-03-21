from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    rate = "5/min"
    scope = "login"


class RegisterRateThrottle(AnonRateThrottle):
    rate = "10/hour"
    scope = "register"
