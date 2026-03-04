from rest_framework import generics, permissions, status, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import get_user_model

# Import models from other apps
from exams.models import Exam
from assessments.models import ExamSession
from certificates.models import Certificate

from .serializers import (
    RegisterSerializer, 
    CustomTokenObtainPairSerializer, 
    StudentListSerializer, # Renamed from CandidateListSerializer
    UserSerializer
)

User = get_user_model()

# --- 1. User Management (CRUD for Admin) ---
class UserViewSet(viewsets.ModelViewSet):
    """
    Admin-only endpoint to manage all users (Students, Teachers, Admins).
    """
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAdminUser]

    def perform_create(self, serializer):
        # Hash password when Admin creates a user manually
        user = serializer.save()
        if 'password' in self.request.data:
            user.set_password(self.request.data['password'])
            user.save()

    def perform_update(self, serializer):
        # Hash password if it is being updated
        user = serializer.save()
        if 'password' in self.request.data and self.request.data['password']:
            user.set_password(self.request.data['password'])
            user.save()

# --- 2. Authentication Views ---
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

class CustomLoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

# --- 3. Dashboard Stats ---
class AdminStatsView(APIView):
    permission_classes = [permissions.IsAdminUser]
    
    def get(self, request):
        stats = {
            "total_exams": Exam.objects.count(),
            # Updated to filter by 'student'
            "total_candidates": User.objects.filter(role='student').count(),
            "pending_grading": ExamSession.objects.filter(end_time__isnull=False, is_graded=False).count(),
            "issued_certificates": Certificate.objects.count(),
        }
        return Response(stats)

# --- 4. Student List View (Formerly CandidateListView) ---
class StudentListView(generics.ListAPIView):
    """
    Returns a list of all students with their exam statistics.
    Only accessible by Admins.
    """
    serializer_class = StudentListSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        # Filter for users with role 'student'
        return User.objects.filter(role='student').order_by('-date_joined')