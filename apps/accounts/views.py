from django.conf import settings
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.audit.services import log_action
from apps.core.throttling import LoginRateThrottle, RegisterRateThrottle, TokenRefreshRateThrottle, ChangePasswordRateThrottle

from .models import CustomUser
from .serializers import ChangePasswordSerializer, RegisterSerializer, SocialAuthSerializer, UserSerializer
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
        role = serializer.validated_data.get("role", "customer")

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
