from django.contrib.auth import authenticate
from rest_framework import serializers

from .models import CustomUser


def register_user(email, first_name, last_name, password, **kwargs):
    if CustomUser.objects.filter(email=email).exists():
        raise serializers.ValidationError({"email": "A user with this email already exists."})
    user = CustomUser.objects.create_user(
        email=email,
        first_name=first_name,
        last_name=last_name,
        password=password,
        **kwargs,
    )
    return user


def change_password(user, old_password, new_password):
    if not user.check_password(old_password):
        raise serializers.ValidationError({"old_password": "Wrong password."})
    user.set_password(new_password)
    user.save(update_fields=["password"])
    return user


def update_user(user, **kwargs):
    for attr, value in kwargs.items():
        setattr(user, attr, value)
    user.save()
    return user
