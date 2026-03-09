from rest_framework import generics, permissions, status, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import get_user_model

# Import models from other apps
from exams.models import Exam
from assessments.models import ExamSession
from certificates.models import Certificate
from cores.models import AuditLog

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
    Provides standard CRUD for users:
    GET /api/users/ - List users
    POST /api/users/ - Create user
    GET /api/users/{id}/ - Retrieve user
    PATCH /api/users/{id}/ - Update role or competencies
    DELETE /api/users/{id}/ - Remove user
    """
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAdminUser]

    def perform_create(self, serializer):
        # Hash password and log the creation
        user = serializer.save()
        password = self.request.data.get('password')
        if password:
            user.set_password(password)
            user.save()
        
        AuditLog.objects.create(
            actor=self.request.user,
            action='CREATE',
            target_model='User',
            target_object_id=user.id,
            details=f"Created user {user.email} with role {user.role}"
        )

    def perform_update(self, serializer):
        # Log updates to roles or competencies
        user = serializer.save()
        password = self.request.data.get('password')
        if password:
            user.set_password(password)
            user.save()

        AuditLog.objects.create(
            actor=self.request.user,
            action='UPDATE',
            target_model='User',
            target_object_id=user.id,
            details=f"Updated user {user.email}"
        )

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