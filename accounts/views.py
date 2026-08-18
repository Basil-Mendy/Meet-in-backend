import re
import random
from django.core.mail import send_mail
from django.conf import settings
from django.db import IntegrityError
from rest_framework import generics, status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .serializers import RegisterSerializer, ProfileSerializer
from .models import User, Profile
from .serializers import VerificationRequestSerializer
from .models import VerificationRequest


class CustomTokenObtainPairView(TokenObtainPairView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            email = request.data.get("email")
            user = User.objects.filter(email=email).first()
            if user:
                admin_role = getattr(user, "admin_role", None)
                role_payload = {
                    "is_super_admin": bool(admin_role and admin_role.is_super_admin) if admin_role else False,
                    "can_manage_schools": bool(admin_role and admin_role.can_manage_schools) if admin_role else True,
                    "can_verify_users": bool(admin_role and admin_role.can_verify_users) if admin_role else True,
                    "can_manage_forums": bool(admin_role and admin_role.can_manage_forums) if admin_role else True,
                } if admin_role else None
                user_payload = {
                    "id": str(user.id),
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "phone": user.phone,
                    "is_verified": user.is_verified,
                    "is_staff": user.is_staff,
                    "is_superuser": user.is_superuser,
                    "is_admin": bool(admin_role or user.is_staff or user.is_superuser),
                    "is_super_admin": bool((admin_role and admin_role.is_super_admin) or user.is_superuser),
                    "admin_role": role_payload,
                }
                response.data["user"] = user_payload
                response.data["is_staff"] = user.is_staff
                response.data["is_superuser"] = user.is_superuser
                response.data["is_admin"] = bool(admin_role or user.is_staff or user.is_superuser)
                response.data["is_super_admin"] = bool((admin_role and admin_role.is_super_admin) or user.is_superuser)
                response.data["admin_role"] = role_payload
        return response


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            serializer.save()
        except IntegrityError as exc:
            error_message = str(exc)
            if "accounts_user.phone" in error_message:
                return Response({"phone": ["A user with this phone number already exists."]}, status=status.HTTP_400_BAD_REQUEST)
            if "accounts_user.email" in error_message:
                return Response({"email": ["A user with this email address already exists."]}, status=status.HTTP_400_BAD_REQUEST)
            return Response({"detail": "Registration failed due to duplicate account information."}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class MyProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = request.user.profile
        profile_data = ProfileSerializer(profile, context={"request": request}).data

        user = request.user

        # Get latest verification request status if any
        latest_verification = VerificationRequest.objects.filter(user=user).order_by("-submitted_at").first()
        verification_status = latest_verification.status if latest_verification else None

        # Merge user fields with profile fields so frontend can read both from one endpoint
        admin_role = getattr(user, "admin_role", None)
        if profile_data.get("photo") and not str(profile_data["photo"]).startswith("http"):
            profile_data["photo"] = request.build_absolute_uri(profile.photo.url) if profile.photo else None

        data = {
            **profile_data,
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": getattr(user, "phone", None),
            "is_verified": getattr(user, "is_verified", False),
            "is_staff": getattr(user, "is_staff", False),
            "is_superuser": getattr(user, "is_superuser", False),
            "is_admin": bool(admin_role or user.is_staff or user.is_superuser),
            "is_super_admin": bool((admin_role and admin_role.is_super_admin) or user.is_superuser),
            "admin_role": {
                "is_super_admin": bool(admin_role and admin_role.is_super_admin) if admin_role else False,
                "can_manage_schools": bool(admin_role and admin_role.can_manage_schools) if admin_role else True,
                "can_verify_users": bool(admin_role and admin_role.can_verify_users) if admin_role else True,
                "can_manage_forums": bool(admin_role and admin_role.can_manage_forums) if admin_role else True,
            } if admin_role else None,
            "verification_status": verification_status,
        }

        return Response(data)


class PublicProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        profile = getattr(user, "profile", None)
        profile_data = ProfileSerializer(profile, context={"request": request}).data if profile else {}

        if profile_data.get("photo") and not str(profile_data["photo"]).startswith("http"):
            profile_data["photo"] = request.build_absolute_uri(profile.photo.url) if profile and profile.photo else None

        admin_role = getattr(user, "admin_role", None)
        latest_verification = VerificationRequest.objects.filter(user=user).order_by("-submitted_at").first()
        verification_status = latest_verification.status if latest_verification else None

        data = {
            **profile_data,
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": getattr(user, "phone", None),
            "is_verified": getattr(user, "is_verified", False),
            "is_staff": getattr(user, "is_staff", False),
            "is_superuser": getattr(user, "is_superuser", False),
            "is_admin": bool(admin_role or user.is_staff or user.is_superuser),
            "is_super_admin": bool((admin_role and admin_role.is_super_admin) or user.is_superuser),
            "admin_role": {
                "is_super_admin": bool(admin_role and admin_role.is_super_admin) if admin_role else False,
                "can_manage_schools": bool(admin_role and admin_role.can_manage_schools) if admin_role else True,
                "can_verify_users": bool(admin_role and admin_role.can_verify_users) if admin_role else True,
                "can_manage_forums": bool(admin_role and admin_role.can_manage_forums) if admin_role else True,
            } if admin_role else None,
            "verification_status": verification_status,
        }

        return Response(data)


class CompleteProfileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def put(self, request):
        profile = request.user.profile

        user_locked_fields = ["first_name", "last_name"]
        for field in user_locked_fields:
            if field in request.data:
                current_value = str(getattr(request.user, field, "") or "").strip()
                next_value = str(request.data.get(field, "") or "").strip()
                if profile.is_completed and next_value and current_value.lower() != next_value.lower():
                    return Response({field: "This field is locked after profile completion. Please contact support to change it."}, status=status.HTTP_400_BAD_REQUEST)

        profile_locked_fields = {
            "date_of_birth": "Date of birth",
            "gender": "Gender",
            "middle_name": "Middle name",
        }

        if profile.is_completed:
            for field_name, label in profile_locked_fields.items():
                if field_name not in request.data:
                    continue

                current_value = getattr(profile, field_name, None)
                next_value = request.data.get(field_name)
                if field_name == "date_of_birth":
                    current_text = current_value.isoformat() if current_value else ""
                    next_text = str(next_value or "")
                    if next_text and current_text and current_text != next_text:
                        return Response({field_name: f"{label} is locked after profile completion. Please contact support to change it."}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    current_text = str(current_value or "")
                    next_text = str(next_value or "")
                    if next_text and current_text.lower() != next_text.lower():
                        return Response({field_name: f"{label} is locked after profile completion. Please contact support to change it."}, status=status.HTTP_400_BAD_REQUEST)

        # Update user identity fields before profile save when profile is not completed.
        user_updates = {}
        if not profile.is_completed:
            for field in ["first_name", "last_name", "email", "phone"]:
                if field in request.data:
                    new_value = str(request.data.get(field) or "").strip()
                    if new_value:
                        user_updates[field] = new_value

        if user_updates:
            for field, value in user_updates.items():
                setattr(request.user, field, value)
            request.user.save(update_fields=list(user_updates.keys()))

        mutable_data = request.data.copy()
        for field in ["first_name", "last_name"]:
            mutable_data.pop(field, None)

        serializer = ProfileSerializer(
            profile, data=mutable_data, partial=True, context={"request": request}
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProfileStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = request.user.profile

        return Response({
            "is_completed": profile.is_completed,
            "is_verified": request.user.is_verified
        })


class VerificationRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = VerificationRequestSerializer(data=request.data)
        if serializer.is_valid():
            # attach user
            vr = serializer.save(user=request.user)
            # In a production system we'd notify admins via email or an admin dashboard
            return Response(VerificationRequestSerializer(vr).data, status=201)

        return Response(serializer.errors, status=400)


class PasswordResetAccountHintView(APIView):
    def post(self, request):
        email = (request.data.get("email") or "").strip().lower()
        phone = (request.data.get("phone") or "").strip()

        if not email and not phone:
            return Response({"detail": "Email or phone is required."}, status=status.HTTP_400_BAD_REQUEST)

        user = None
        if email:
            user = User.objects.filter(email=email).first()
        if not user and phone:
            user = User.objects.filter(phone=phone).first()

        if not user:
            return Response({"detail": "No account found for that information."}, status=status.HTTP_404_NOT_FOUND)

        full_name = " ".join(filter(None, [user.first_name, user.last_name])).strip() or user.email or user.phone
        return Response({
            "email": user.email,
            "phone": user.phone,
            "full_name": full_name,
        })


class PasswordResetRequestView(APIView):
    def post(self, request):
        email = (request.data.get("email") or "").strip().lower()
        phone = (request.data.get("phone") or "").strip()
        delivery_method = (request.data.get("delivery_method") or "email").strip().lower()

        if delivery_method == "phone":
            if not phone:
                return Response({"detail": "Phone number is required for phone delivery."}, status=status.HTTP_400_BAD_REQUEST)
            user = User.objects.filter(phone=phone).first()
            if not user:
                return Response({"detail": "No account found for that phone number."}, status=status.HTTP_404_NOT_FOUND)
            email = user.email or ""
        else:
            if not email:
                return Response({"detail": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)
            user = User.objects.filter(email=email).first()
            if not user:
                return Response({"detail": "No account found for that email."}, status=status.HTTP_404_NOT_FOUND)
            phone = str(user.phone).strip()

        otp = f"{random.randint(100000, 999999)}"
        request.session["password_reset_email"] = email
        request.session["password_reset_phone"] = phone
        request.session["password_reset_otp"] = otp
        request.session["password_reset_delivery"] = delivery_method

        if delivery_method == "phone":
            if not phone:
                return Response({"detail": "No phone number is available for this account."}, status=status.HTTP_400_BAD_REQUEST)
            message = f"Your ALUMNI password reset OTP is {otp}"
            print(message)
        else:
            send_mail(
                subject="ALUMNI password reset OTP",
                message=f"Your ALUMNI password reset OTP is {otp}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )

        return Response({"detail": "OTP sent successfully."}, status=status.HTTP_200_OK)


class PasswordResetVerifyView(APIView):
    def post(self, request):
        email = (request.data.get("email") or "").strip().lower()
        phone = (request.data.get("phone") or "").strip()
        otp = (request.data.get("otp") or "").strip()

        if not otp:
            return Response({"detail": "OTP is required."}, status=status.HTTP_400_BAD_REQUEST)

        delivery_method = request.session.get("password_reset_delivery")
        session_otp = request.session.get("password_reset_otp")

        if session_otp != otp:
            return Response({"detail": "Invalid or expired OTP."}, status=status.HTTP_400_BAD_REQUEST)

        if delivery_method == "phone":
            session_phone = request.session.get("password_reset_phone")
            if not phone or session_phone != phone:
                return Response({"detail": "Phone and OTP do not match."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            session_email = request.session.get("password_reset_email")
            if not email or session_email != email:
                return Response({"detail": "Email and OTP do not match."}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"detail": "OTP verified."}, status=status.HTTP_200_OK)


class PasswordResetCompleteView(APIView):
    def post(self, request):
        email = (request.data.get("email") or "").strip().lower()
        phone = (request.data.get("phone") or "").strip()
        otp = (request.data.get("otp") or "").strip()
        password = request.data.get("password") or ""

        if not otp or not password:
            return Response({"detail": "OTP and a new password are required."}, status=status.HTTP_400_BAD_REQUEST)

        delivery_method = request.session.get("password_reset_delivery")
        session_otp = request.session.get("password_reset_otp")

        if session_otp != otp:
            return Response({"detail": "Invalid or expired OTP."}, status=status.HTTP_400_BAD_REQUEST)

        if delivery_method == "phone":
            session_phone = request.session.get("password_reset_phone")
            if not phone or session_phone != phone:
                return Response({"detail": "Phone and OTP do not match."}, status=status.HTTP_400_BAD_REQUEST)
            user = User.objects.filter(phone=phone).first()
        else:
            session_email = request.session.get("password_reset_email")
            if not email or session_email != email:
                return Response({"detail": "Email and OTP do not match."}, status=status.HTTP_400_BAD_REQUEST)
            user = User.objects.filter(email=email).first()

        if not user:
            return Response({"detail": "No matching account found."}, status=status.HTTP_404_NOT_FOUND)

        user.set_password(password)
        user.save(update_fields=["password"])
        request.session.pop("password_reset_email", None)
        request.session.pop("password_reset_phone", None)
        request.session.pop("password_reset_otp", None)
        request.session.pop("password_reset_delivery", None)

        return Response({"detail": "Password updated successfully."}, status=status.HTTP_200_OK)
