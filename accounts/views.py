from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .serializers import RegisterSerializer, ProfileSerializer
from .models import User, Profile
from .serializers import VerificationRequestSerializer
from .models import VerificationRequest


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if not serializer.is_valid():
            print(serializer.errors)  # Debug only
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class MyProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = request.user.profile
        profile_data = ProfileSerializer(profile).data

        user = request.user

        # Get latest verification request status if any
        latest_verification = VerificationRequest.objects.filter(user=user).order_by("-submitted_at").first()
        verification_status = latest_verification.status if latest_verification else None

        # Merge user fields with profile fields so frontend can read both from one endpoint
        data = {
            **profile_data,
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": getattr(user, "phone", None),
            "is_verified": getattr(user, "is_verified", False),
            "verification_status": verification_status,
        }

        return Response(data)


class CompleteProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        profile = request.user.profile
        serializer = ProfileSerializer(
            profile, data=request.data, partial=True
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
