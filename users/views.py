from rest_framework import generics, permissions, status, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import get_user_model

# Import models from other apps
from exams.models import Exam
from assessments.models import ExamSession
from certificates.models import Certificate
# --- FIX: Ensure AuditLog is imported ---
from cores.models import AuditLog 

from .serializers import (
    RegisterSerializer, 
    CustomTokenObtainPairSerializer, 
    CandidateListSerializer,
    UserSerializer
)

User = get_user_model()

# --- 2. User Management (CRUD for Admin) ---
class UserViewSet(viewsets.ModelViewSet):
    """
    Admin-only endpoint to manage all users.
    Now includes AUDIT LOGGING.
    """
    queryset = User.objects.all().order_by('-date_joined')
    permission_classes = [permissions.IsAdminUser]

    def get_serializer_class(self):
        if self.action == 'create':
            return RegisterSerializer
        return UserSerializer

    def perform_create(self, serializer):
        user = serializer.save()
        
        # --- AUDIT LOG: CREATE ---
        AuditLog.objects.create(
            actor=self.request.user,
            action='CREATE',
            target_model='User',
            target_object_id=str(user.id),
            details=f"Created new user: {user.email} (Role: {user.role})"
        )

    def perform_update(self, serializer):
        user = serializer.save()
        # Handle password update if present
        if 'password' in self.request.data and self.request.data['password']:
            user.set_password(self.request.data['password'])
            user.save()

        # --- AUDIT LOG: UPDATE ---
        AuditLog.objects.create(
            actor=self.request.user,
            action='UPDATE',
            target_model='User',
            target_object_id=str(user.id),
            details=f"Updated profile for: {user.email}"
        )

    def perform_destroy(self, instance):
        # --- AUDIT LOG: DELETE ---
        AuditLog.objects.create(
            actor=self.request.user,
            action='DELETE',
            target_model='User',
            target_object_id=str(instance.id),
            details=f"Deleted user account: {instance.email}"
        )
        instance.delete()

# --- 3. Authentication Views ---
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

class CustomLoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

# --- 4. Dashboard Stats ---
class AdminStatsView(APIView):
    permission_classes = [permissions.IsAdminUser]
    
    def get(self, request):
        stats = {
            "total_exams": Exam.objects.count(),
            "total_candidates": User.objects.filter(role='candidate').count(),
            "pending_grading": ExamSession.objects.filter(end_time__isnull=False, is_graded=False).count(),
            "issued_certificates": Certificate.objects.count(),
        }
        return Response(stats)

# --- 5. Candidate List View ---
class CandidateListView(generics.ListAPIView):
    serializer_class = CandidateListSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        return User.objects.filter(role='candidate').order_by('-date_joined')

class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

class ExaminerManagementView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = RegisterSerializer 

    def get_queryset(self):
        return User.objects.filter(role='examiner')

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        data['role'] = 'examiner' 
        
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)