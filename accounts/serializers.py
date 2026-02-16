from rest_framework import serializers
from .models import User, Profile
from .models import VerificationRequest


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)
    phone = serializers.CharField(required=True)

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "phone",
            "password",
        ]

    def create(self, validated_data):
        password = validated_data.pop("password")

        user = User.objects.create_user(
            password=password,
            is_verified=False,  # user starts unverified
            **validated_data
        )

        return user


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = [
            "middle_name",
            "date_of_birth",
            "gender",
            "nationality",
            "city",
            "state",
            "photo",
            "occupation",
            "contact_info",
            "is_completed",
        ]
        read_only_fields = ["is_completed"]

    def update(self, instance, validated_data):
        # Update profile fields normally
        profile = super().update(instance, validated_data)

        # Profile completion rules (photo-only updates won't trigger completion check)
        if any(k in validated_data for k in ["date_of_birth", "nationality", "state", "city", "middle_name", "gender"]):
            required_fields = [
                profile.date_of_birth,
                profile.nationality,
                profile.state,
                profile.city,
                profile.photo,
            ]
            profile.is_completed = all(required_fields)
            profile.save()

        return profile


class VerificationRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = VerificationRequest
        fields = ["id", "selfie", "id_document", "id_type", "status", "submitted_at"]
        read_only_fields = ["id", "status", "submitted_at"]
