from django.conf import settings
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.audit.services import log_action
from apps.core.throttling import ChangePasswordRateThrottle, LoginRateThrottle, PasswordResetRateThrottle, RegisterRateThrottle, TokenRefreshRateThrottle

from .models import CustomUser
from .password_reset import confirm_password_reset, request_password_reset, validate_reset_token
from .serializers import (
    ChangePasswordSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    SocialAuthSerializer,
    UserSerializer,
)
from .services import change_password


class SocialAuthView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        import requests as http_requests

        serializer = SocialAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        provider = serializer.validated_data["provider"]
        token = serializer.validated_data["token"]
        # SECURITY FIX (FINDING-009): Always force 'customer' role for social login.
        # Role escalation (to organizer/admin) must be done through admin approval.
        # The 'role' field from the request is intentionally IGNORED.
        role = "customer"

        user_info = self._verify_google(token, http_requests) if provider == "google" else self._verify_facebook(token, http_requests)

        if not user_info or not user_info.get("email"):
            return Response(
                {"detail": "Could not verify token with provider."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = self._get_or_create_user(user_info, role)

        refresh = RefreshToken.for_user(user)
        access = refresh.access_token

        log_action(action="social_login", actor=user, target=user, request=request)

        response = Response(
            {"access": str(access), "user": UserSerializer(user).data},
            status=status.HTTP_200_OK,
        )
        response.set_cookie(
            key="refresh_token",
            value=str(refresh),
            httponly=True,
            samesite="Lax",
            secure=not settings.DEBUG,
            max_age=7 * 24 * 60 * 60,
            path="/",
        )
        return response

    def _verify_google(self, token, http_requests):
        try:
            # Step 1: validate the token audience (prevents confused deputy attack)
            google_client_id = settings.GOOGLE_CLIENT_ID
            if not google_client_id:
                return None  # refuse auth when audience validation is not configured

            tokeninfo_resp = http_requests.get(
                "https://www.googleapis.com/oauth2/v3/tokeninfo",
                params={"access_token": token},
                timeout=10,
            )
            if tokeninfo_resp.status_code != 200:
                return None
            tokeninfo = tokeninfo_resp.json()
            # aud or azp must match our client_id
            if tokeninfo.get("aud") != google_client_id and tokeninfo.get("azp") != google_client_id:
                return None

            # Step 2: fetch user profile
            resp = http_requests.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            return {
                "email": data.get("email"),
                "first_name": data.get("given_name", ""),
                "last_name": data.get("family_name", ""),
            }
        except Exception:
            return None

    def _verify_facebook(self, token, http_requests):
        try:
            facebook_app_id = settings.FACEBOOK_APP_ID
            facebook_app_secret = settings.FACEBOOK_APP_SECRET
            if not facebook_app_id or not facebook_app_secret:
                return None  # refuse auth when audience validation is not configured

            # Step 1: validate token's app via debug_token (prevents confused deputy)
            debug_resp = http_requests.get(
                "https://graph.facebook.com/debug_token",
                params={
                    "input_token": token,
                    "access_token": f"{facebook_app_id}|{facebook_app_secret}",
                },
                timeout=10,
            )
            if debug_resp.status_code != 200:
                return None
            debug_data = debug_resp.json().get("data", {})
            if not debug_data.get("is_valid"):
                return None
            if str(debug_data.get("app_id")) != str(facebook_app_id):
                return None

            # Step 2: fetch user profile
            resp = http_requests.get(
                "https://graph.facebook.com/me",
                params={"fields": "id,email,first_name,last_name", "access_token": token},
                timeout=10,
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            return {
                "email": data.get("email"),
                "first_name": data.get("first_name", ""),
                "last_name": data.get("last_name", ""),
            }
        except Exception:
            return None

    def _get_or_create_user(self, user_info, role):
        email = user_info["email"]
        user, created = CustomUser.objects.get_or_create(
            email=email,
            defaults={
                "first_name": user_info.get("first_name", ""),
                "last_name": user_info.get("last_name", ""),
                "role": role,
                "is_active": True,
            },
        )
        return user


class LoginView(TokenObtainPairView):
    authentication_classes = []
    throttle_classes = [LoginRateThrottle]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            raise InvalidToken(e.args[0])

        user = serializer.user
        data = serializer.validated_data
        access = data.get("access")
        refresh = data.get("refresh")

        log_action(
            action="user_login",
            actor=user,
            target=user,
            request=request,
        )

        from .serializers import UserSerializer
        response = Response({
            "access": str(access),
            "user": UserSerializer(user).data,
        }, status=status.HTTP_200_OK)
        response.set_cookie(
            key="refresh_token",
            value=str(refresh),
            httponly=True,
            samesite="Lax",
            secure=not settings.DEBUG,
            max_age=7 * 24 * 60 * 60,
            path="/",
        )
        return response


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [RegisterRateThrottle]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        log_action(
            action="user_register",
            actor=user,
            target=user,
            request=request,
        )

        output = UserSerializer(user)
        return Response(output.data, status=status.HTTP_201_CREATED)


class TokenRefreshCookieView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [TokenRefreshRateThrottle]

    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get("refresh_token")
        if not refresh_token:
            return Response(
                {"error": "Refresh token not found.", "code": "no_refresh_token"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            token = RefreshToken(refresh_token)
            access = str(token.access_token)
            new_refresh = str(token)

            response = Response({"access": access}, status=status.HTTP_200_OK)
            response.set_cookie(
                key="refresh_token",
                value=new_refresh,
                httponly=True,
                samesite="Lax",
                secure=not settings.DEBUG,
                max_age=7 * 24 * 60 * 60,
                path="/",
            )
            return response
        except TokenError as e:
            return Response(
                {"error": str(e), "code": "invalid_refresh_token"},
                status=status.HTTP_401_UNAUTHORIZED,
            )


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get("refresh_token")
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except TokenError:
                pass

        log_action(
            action="user_logout",
            actor=request.user,
            target=request.user,
            request=request,
        )

        response = Response(status=status.HTTP_204_NO_CONTENT)
        response.delete_cookie("refresh_token", path="/")
        return response


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ChangePasswordRateThrottle]

    def post(self, request, *args, **kwargs):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        change_password(
            user=request.user,
            old_password=serializer.validated_data["old_password"],
            new_password=serializer.validated_data["new_password"],
        )
        return Response({"detail": "Password changed successfully."}, status=status.HTTP_200_OK)


class PasswordResetRequestView(APIView):
    """POST /api/v1/auth/password-reset/request/ — solicita link de recuperação."""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [PasswordResetRateThrottle]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_password_reset(email=serializer.validated_data["email"])
        # Sempre retorna 200 para não revelar se email existe
        return Response(
            {"detail": "Se este email estiver cadastrado, você receberá as instruções em breve."},
            status=status.HTTP_200_OK,
        )


class PasswordResetValidateView(APIView):
    """GET /api/v1/auth/password-reset/validate/{token}/ — verifica se token é válido."""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, token):
        if validate_reset_token(token):
            return Response({"valid": True}, status=status.HTTP_200_OK)
        return Response(
            {"valid": False, "detail": "Link inválido ou expirado."},
            status=status.HTTP_400_BAD_REQUEST,
        )


class PasswordResetConfirmView(APIView):
    """POST /api/v1/auth/password-reset/confirm/ — confirma nova senha."""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [PasswordResetRateThrottle]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        confirm_password_reset(
            token=serializer.validated_data["token"],
            new_password=serializer.validated_data["new_password"],
        )
        log_action(action="password_reset", actor=None, target=None, request=request)
        return Response(
            {"detail": "Senha redefinida com sucesso. Um código de confirmação foi enviado ao seu email."},
            status=status.HTTP_200_OK,
        )
