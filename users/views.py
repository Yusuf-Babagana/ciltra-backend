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
    CandidateListSerializer,
    UserSerializer  # <--- Make sure this is imported!
)

# --- CRITICAL FIX: Define User BEFORE using it in classes ---
User = get_user_model()

# --- 1. User Management (CRUD for Admin) ---
class UserViewSet(viewsets.ModelViewSet):
    """
    Admin-only endpoint to manage all users (Candidates, Examiners, Admins).
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
            "total_candidates": User.objects.filter(role='candidate').count(),
            "pending_grading": ExamSession.objects.filter(end_time__isnull=False, is_graded=False).count(),
            "issued_certificates": Certificate.objects.count(),
        }
        return Response(stats)

# --- 4. Candidate List View ---
class CandidateListView(generics.ListAPIView):
    """
    Returns a list of all candidates with their exam statistics.
    Only accessible by Admins.
    """
    serializer_class = CandidateListSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        return User.objects.filter(role='candidate').order_by('-date_joined')


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    Allows any authenticated user to view and update their own profile.
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        # Magic: Simply returns the user who is currently logged in
        return self.request.user



class ExaminerManagementView(generics.ListCreateAPIView):
    """
    GET: List all examiners
    POST: Create a new examiner
    """
    permission_classes = [permissions.IsAdminUser] # Only Admin can access
    serializer_class = RegisterSerializer 

    def get_queryset(self):
        # Only return users who are examiners
        return User.objects.filter(role='examiner')

    def create(self, request, *args, **kwargs):
        # Force the role to be 'examiner' when Admin creates one
        data = request.data.copy()
        data['role'] = 'examiner' 
        
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        # Return the clean user data (without password)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

