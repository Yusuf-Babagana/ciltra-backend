from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import Exam, Question, Option, ExamCategory
from assessments.models import ExamSession, StudentAnswer
from .serializers import (
    ExamSerializer, ExamDetailSerializer, ExamListSerializer,
    QuestionSerializer, ExamCategorySerializer, OptionSerializer,
    ExamSessionStartSerializer, ExamSubmitSerializer
)

import csv
import io

import os
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from django.core.management import call_command

from rest_framework.response import Response
from django.core.management import call_command
from django.http import FileResponse


import shutil

# --- FIX 1: Import JSONParser ---
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

class ExamViewSet(viewsets.ModelViewSet):
    queryset = Exam.objects.all().order_by('-created_at')
    filter_backends = [filters.SearchFilter]
    search_fields = ['title', 'category__name']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ExamDetailSerializer
        if self.action == 'list':
            if self.request.user.is_staff:
                return ExamSerializer
            return ExamListSerializer
        return ExamSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        if self.action in ['start_exam', 'submit_exam_session']:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAdminUser()]

    @action(detail=True, methods=['post'], url_path='start')
    def start_exam(self, request, pk=None):
        exam = self.get_object()
        user = request.user
        active_session = ExamSession.objects.filter(user=user, exam=exam, end_time__isnull=True).first()
        if not active_session:
            active_session = ExamSession.objects.create(user=user, exam=exam)
        serializer = ExamSessionStartSerializer(active_session)
        return Response(serializer.data)

    # --- NEW: Assign Student (Grant Access) ---
    @action(detail=True, methods=['post'], url_path='assign-student')
    def assign_student(self, request, pk=None):
        """
        Manually grants an exam to a student (creates a free payment record).
        """
        exam = self.get_object()
        email = request.data.get('email')
        
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": f"User with email '{email}' not found."}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if already assigned
        from payments.models import Payment
        if Payment.objects.filter(user=user, exam=exam, status='success').exists():
             return Response({"message": "User already has access to this exam."}, status=status.HTTP_200_OK)

        # Create a "Grant" Payment
        Payment.objects.create(
            user=user,
            exam=exam,
            amount=0.00,
            reference=f"ADMIN-GRANT-{int(timezone.now().timestamp())}",
            status='success',
            verified_at=timezone.now()
        )
        
        return Response({"status": f"Successfully assigned '{exam.title}' to {user.first_name}"})

    @action(detail=True, methods=['post'], url_path='assign-questions')
    def assign_questions(self, request, pk=None):
        exam = self.get_object()
        question_ids = request.data.get('question_ids', [])
        count = Question.objects.filter(id__in=question_ids).update(exam=exam)
        return Response({"status": f"Added {count} questions to {exam.title}"})

    @action(detail=True, methods=['post'], url_path='remove-questions')
    def remove_questions(self, request, pk=None):
        question_ids = request.data.get('question_ids', [])
        Question.objects.filter(id__in=question_ids, exam=self.get_object()).update(exam=None)
        return Response({"status": "Questions returned to bank"})

# ... (QuestionViewSet and CategoryViewSet remain unchanged) ...
class QuestionViewSet(viewsets.ModelViewSet):
    queryset = Question.objects.all().order_by('-id')
    serializer_class = QuestionSerializer
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [filters.SearchFilter]
    search_fields = ['text', 'category']
    parser_classes = (MultiPartParser, FormParser, JSONParser) 

    def get_queryset(self):
        queryset = super().get_queryset()
        exam_id = self.request.query_params.get('exam_id')
        if exam_id:
            queryset = queryset.filter(exam_id=exam_id)
        return queryset

    @action(detail=False, methods=['post'], url_path='bulk-upload')
    def bulk_upload(self, request):
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            decoded_file = file_obj.read().decode('utf-8')
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)
            created_count = 0
            for row in reader:
                question = Question.objects.create(
                    text=row['question_text'],
                    question_type=row.get('question_type', 'mcq').lower(),
                    category=row.get('category', 'General'),
                    difficulty=row.get('difficulty', 'medium').lower(),
                    points=int(row.get('points', 1)) 
                )
                if question.question_type == 'mcq':
                    raw_options = row.get('options', '').split('|')
                    correct_ans_text = row.get('correct_answer', '').strip().lower()
                    for opt_text in raw_options:
                        clean_text = opt_text.strip()
                        if clean_text:
                            is_correct = (clean_text.lower() == correct_ans_text)
                            Option.objects.create(question=question, text=clean_text, is_correct=is_correct)
                created_count += 1
            return Response({"status": f"Successfully uploaded {created_count} questions"}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = ExamCategory.objects.all()
    serializer_class = ExamCategorySerializer
    permission_classes = [permissions.IsAdminUser]

    

class QuestionViewSet(viewsets.ModelViewSet):
    queryset = Question.objects.all().order_by('-id')
    serializer_class = QuestionSerializer
    permission_classes = [permissions.IsAdminUser]
    
    # Enable Search and Filtering for the Question Bank
    filter_backends = [filters.SearchFilter]
    search_fields = ['text', 'category']

    def get_queryset(self):
        queryset = super().get_queryset()
        # Filter by Exam if provided ?exam_id=1
        exam_id = self.request.query_params.get('exam_id')
        if exam_id:
            queryset = queryset.filter(exam_id=exam_id)
        return queryset

    # --- FIX 2: Add JSONParser here so regular API requests work ---
    parser_classes = (MultiPartParser, FormParser, JSONParser) 

    @action(detail=False, methods=['post'], url_path='bulk-upload')
    def bulk_upload(self, request):
        """
        Upload questions via CSV.
        Expected CSV Header: question_text, question_type, category, difficulty, points, options, correct_answer
        """
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            decoded_file = file_obj.read().decode('utf-8')
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)
            
            created_count = 0
            
            for row in reader:
                # 1. Create Question
                question = Question.objects.create(
                    text=row['question_text'],
                    question_type=row.get('question_type', 'mcq').lower(),
                    category=row.get('category', 'General'),
                    difficulty=row.get('difficulty', 'medium').lower(),
                    points=int(row.get('points', 1)) 
                )

                # 2. Handle Options (for MCQs)
                if question.question_type == 'mcq':
                    raw_options = row.get('options', '').split('|')
                    correct_ans_text = row.get('correct_answer', '').strip().lower()

                    for opt_text in raw_options:
                        clean_text = opt_text.strip()
                        if clean_text:
                            is_correct = (clean_text.lower() == correct_ans_text)
                            Option.objects.create(
                                question=question,
                                text=clean_text,
                                is_correct=is_correct
                            )
                
                created_count += 1
                
            return Response({"status": f"Successfully uploaded {created_count} questions"}, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = ExamCategory.objects.all()
    serializer_class = ExamCategorySerializer
    permission_classes = [permissions.IsAdminUser]





# --- Backup Management Views ---

@api_view(['GET'])
@permission_classes([IsAdminUser])
def list_backups(request):
    backup_dir = os.path.join(settings.BASE_DIR, 'backups')
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
        return Response([])
    
    files = []
    for f in os.listdir(backup_dir):
        if f.endswith('.sqlite3'):
            path = os.path.join(backup_dir, f)
            stats = os.stat(path)
            
            # --- FIX: Convert timestamp to a readable ISO string ---
            from datetime import datetime
            dt_object = datetime.fromtimestamp(stats.st_mtime)
            readable_date = dt_object.isoformat() 

            files.append({
                "filename": f,
                "size": f"{round(stats.st_size / 1024, 2)} KB", # Size as a string
                "created_at": readable_date  # ISO String
                })
    
    files.sort(key=lambda x: x['created_at'], reverse=True)
    return Response(files)

@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_backup_view(request):
    try:
        from scripts.backup_local import run_backup
        run_backup()
        return Response({
            "status": "success",
            "message": "System snapshot created successfully."
        })
    except Exception as e:
        return Response({"status": "error", "message": str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAdminUser])
def download_backup(request, filename):
    backup_file = os.path.join(settings.BASE_DIR, 'backups', filename)
    if os.path.exists(backup_file):
        return FileResponse(open(backup_file, 'rb'), as_attachment=True)
    return Response({"error": "File not found"}, status=404)

@api_view(['DELETE'])
@permission_classes([IsAdminUser])
def delete_backup(request, filename):
    backup_file = os.path.join(settings.BASE_DIR, 'backups', filename)
    if os.path.exists(backup_file):
        os.remove(backup_file)
        return Response({"message": "Backup deleted"})
    return Response({"error": "File not found"}, status=404)

@api_view(['POST'])
@permission_classes([IsAdminUser])
def perform_restore(request):
    filename = request.data.get('filename')
    if not filename:
        return Response({"error": "No filename provided"}, status=400)
    try:
        # Note: 'restore_db' must be a custom management command you've created
        call_command('restore_db', filename)
        return Response({"message": "Database successfully restored."})
    except Exception as e:
        return Response({"error": str(e)}, status=500)