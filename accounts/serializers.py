from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from .models import User, Profile
from .models import VerificationRequest


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)
    phone = serializers.CharField(
        required=True,
        validators=[UniqueValidator(queryset=User.objects.all(), message="A user with this phone number already exists.")],
    )

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
            "nickname",
            "date_of_birth",
            "gender",
            "nationality",
            "country",
            "state",
            "lga",
            "city",
            "photo",
            "occupation",
            "contact_info",
            "is_completed",
        ]
        read_only_fields = ["is_completed"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")

        if instance.photo and request is not None:
            photo_value = data.get("photo")
            if not photo_value or not str(photo_value).startswith("http"):
                data["photo"] = request.build_absolute_uri(instance.photo.url)

        return data

    def validate(self, attrs):
        instance = self.instance
        if not instance or not instance.is_completed:
            return attrs

        locked_fields = {
            "date_of_birth": "Date of birth",
            "gender": "Gender",
            "middle_name": "Middle name",
        }

        for field_name, label in locked_fields.items():
            if field_name not in attrs:
                continue

            current_value = getattr(instance, field_name, None)
            new_value = attrs.get(field_name)

            if field_name == "date_of_birth":
                current_string = current_value.isoformat() if current_value else ""
                new_string = str(new_value) if new_value else ""
                if new_string and current_string != new_string:
                    raise serializers.ValidationError({field_name: f"{label} is locked after profile completion. Please contact support to change it."})
            else:
                current_string = str(current_value or "")
                new_string = str(new_value or "")
                if new_string and current_string.lower() != new_string.lower():
                    raise serializers.ValidationError({field_name: f"{label} is locked after profile completion. Please contact support to change it."})

        return attrs

    def update(self, instance, validated_data):
        profile = super().update(instance, validated_data)

        if any(k in validated_data for k in ["date_of_birth", "nationality", "country", "state", "lga", "city", "middle_name", "gender", "photo"]):
            required_fields = [
                profile.date_of_birth,
                profile.nationality,
                profile.country,
                profile.state,
                profile.lga,
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
