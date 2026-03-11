from rest_framework import generics, permissions, status, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string
import csv
import string
import random
from rest_framework.decorators import action, api_view

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
    # queryset = User.objects.all().order_by('-date_joined') # Removed static queryset in favor of get_queryset
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        """
        CPT-Integrated: Supports fetching trashed (deactivated) users via ?trashed=true.
        """
        show_trashed = self.request.query_params.get('trashed', 'false') == 'true'
        if show_trashed:
            return User.objects.filter(is_active=False).order_by('-date_joined')
        return User.objects.filter(is_active=True).order_by('-date_joined')

    def destroy(self, request, *args, **kwargs):
        """
        CPT-Integrated: Implements Soft Delete to maintain 15/65/20 data integrity.
        """
        user = self.get_object()
        user_email = user.email
        
        # Soft Delete (Deactivate)
        user.is_active = False
        user.save()

        # Log the deletion in AuditLog
        AuditLog.objects.create(
            actor=request.user,
            action='DELETE',
            target_model='User',
            target_object_id=str(user.id),
            details=f"Deleted/Deactivated user: {user_email}"
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path='restore')
    def restore(self, request, pk=None):
        """
        CPT-Integrated: Restores a deactivated user account.
        """
        user = self.get_object()
        user.is_active = True
        user.save()

        AuditLog.objects.create(
            actor=request.user,
            action='RESTORE',
            target_model='User',
            target_object_id=str(user.id),
            details=f"Restored user account: {user.email}"
        )
        return Response({"message": "User restored successfully"}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='toggle-status')
    def toggle_status(self, request, pk=None):
        """
        Dedicated endpoint to Suspend or Activate a user.
        Logs the specific administrative action to the AuditLog.
        """
        user = self.get_object()
        
        # Prevent self-suspension
        if user == request.user:
            return Response({"error": "You cannot suspend your own account."}, status=status.HTTP_400_BAD_REQUEST)

        user.is_active = not user.is_active
        user.save()
        
        action_type = "ACTIVATE" if user.is_active else "SUSPEND"
        
        # --- ENHANCED AUDIT LOG ---
        AuditLog.objects.create(
            actor=request.user,
            action=action_type,
            target_model='User',
            target_object_id=str(user.id),
            details=f"{action_type}: {user.email}. Status changed by Admin."
        )

        return Response({
            "status": "success",
            "is_active": user.is_active,
            "message": f"User account has been {action_type.lower()}d."
        })

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


@api_view(['POST'])
def bulk_register_students(request):
    """
    CPT-Integrated: Bulk registers students via CSV upload.
    Generates random passwords and assigns 'student' role.
    """
    csv_file = request.FILES.get('file')
    if not csv_file:
        return Response({"error": "No file uploaded"}, status=400)

    try:
        decoded_file = csv_file.read().decode('utf-8').splitlines()
        reader = csv.DictReader(decoded_file)
        
        created_count = 0
        errors = []

        for row in reader:
            email = row.get('email', '').strip()
            full_name = row.get('full_name', '').strip()
            
            if not email:
                continue

            if User.objects.filter(email=email).exists():
                errors.append(f"Email {email} already exists.")
                continue

            # Generate a random 8-character password
            temp_password = get_random_string(8)
            
            try:
                # Note: first_name and last_name split logic
                name_parts = full_name.split(' ')
                first_name = name_parts[0] if name_parts else ""
                last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ""

                user = User.objects.create_user(
                    username=email, # Using email as username for simplicity
                    email=email,
                    password=temp_password,
                    first_name=first_name,
                    last_name=last_name,
                    role='student' # Fixed to 'student' to match existing role
                )
                created_count += 1
            except Exception as e:
                errors.append(f"Error creating {email}: {str(e)}")

        return Response({
            "status": "success",
            "message": f"Successfully registered {created_count} students.",
            "skipped": errors
        })
    except Exception as e:
        return Response({"error": f"Failed to process CSV: {str(e)}"}, status=500)