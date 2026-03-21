from django.conf import settings
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.audit.services import log_action
from apps.core.throttling import LoginRateThrottle, RegisterRateThrottle

from .models import CustomUser
from .serializers import ChangePasswordSerializer, RegisterSerializer, UserSerializer
from .services import change_password


class LoginView(TokenObtainPairView):
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

        response = Response({"access": str(access)}, status=status.HTTP_200_OK)
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

    def post(self, request, *args, **kwargs):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        change_password(
            user=request.user,
            old_password=serializer.validated_data["old_password"],
            new_password=serializer.validated_data["new_password"],
        )
        return Response({"detail": "Password changed successfully."}, status=status.HTTP_200_OK)
