from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAdminUser
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.conf import settings
from django.http import FileResponse, HttpResponse
from django.core.management import call_command

import csv
import io
import os
import shutil
from datetime import datetime

# Internal Project Imports
# NOTE: LanguagePair lives in cores.models, NOT in exams.models
from .models import Exam, Question, Option, ExamCategory, ExaminerAssignment
from assessments.models import ExamSession, StudentAnswer
from cores.models import AuditLog, LanguagePair  # <-- CORRECT import location
from .serializers import (
    ExamSerializer, ExamDetailSerializer, ExamListSerializer,
    QuestionSerializer, ExamCategorySerializer, OptionSerializer,
    ExamSessionStartSerializer, ExamSubmitSerializer, LanguagePairSerializer
)


# ===========================================================================
# EXAM VIEWSET
# ===========================================================================
class ExamViewSet(viewsets.ModelViewSet):
    queryset = Exam.objects.all().order_by('-created_at')
    filter_backends = [filters.SearchFilter]
    search_fields = ['title', 'category__name']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ExamDetailSerializer
        if self.action == 'list':
            return ExamSerializer if self.request.user.is_staff else ExamListSerializer
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
        active_session = ExamSession.objects.filter(
            user=request.user, exam=exam, end_time__isnull=True
        ).first()
        if not active_session:
            active_session = ExamSession.objects.create(user=request.user, exam=exam)
        return Response(ExamSessionStartSerializer(active_session).data)

    @action(detail=True, methods=['post'], url_path='assign-student')
    def assign_student(self, request, pk=None):
        """Manually grants an exam to a student (creates a free payment record)."""
        exam = self.get_object()
        email = request.data.get('email')
        from django.contrib.auth import get_user_model
        User = get_user_model()

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": f"User with email '{email}' not found."}, status=status.HTTP_404_NOT_FOUND)

        from payments.models import Payment
        if Payment.objects.filter(user=user, exam=exam, status='success').exists():
            return Response({"message": "User already has access."}, status=status.HTTP_200_OK)

        Payment.objects.create(
            user=user, exam=exam, amount=0.00,
            reference=f"ADMIN-GRANT-{int(timezone.now().timestamp())}",
            status='success', verified_at=timezone.now()
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

    @action(detail=True, methods=['post'], url_path='assign-examiner')
    def assign_examiner(self, request, pk=None):
        """Assigns an examiner to an exam with a role and conflict-of-interest declaration."""
        exam = self.get_object()
        user_id = request.data.get('user_id')
        role = request.data.get('role', 'content')
        no_conflict = request.data.get('has_declared_no_conflict', False)

        if not user_id:
            return Response({"error": "User ID is required"}, status=400)

        assignment, created = ExaminerAssignment.objects.update_or_create(
            exam=exam, user_id=user_id,
            defaults={'role': role, 'has_declared_no_conflict': no_conflict}
        )

        AuditLog.objects.create(
            actor=request.user, action='UPDATE', target_model='Exam',
            target_object_id=str(exam.id),
            details=f"Assigned {assignment.user.email} as {role} to {exam.title}"
        )
        return Response({"status": "Examiner assigned successfully"})


# ===========================================================================
# QUESTION VIEWSET
# ===========================================================================
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
        """
        CPT-Integrated: Bulk upload questions (MCQ or Theory) via CSV.
        Required CSV headers: question_text, question_type, section, points,
        difficulty, category, options (semicolon-separated for MCQ), correct_answer.
        """
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({"error": "No CSV file uploaded."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            decoded_file = file_obj.read().decode('utf-8')
            reader = csv.DictReader(io.StringIO(decoded_file))
            created_count = 0
            errors = []

            for row_idx, row in enumerate(reader, start=1):
                try:
                    question_text = row.get('question_text', '').strip()
                    if not question_text:
                        continue

                    q_type = row.get('question_type', 'mcq').lower()
                    question = Question.objects.create(
                        text=question_text,
                        question_type=q_type,
                        section=row.get('section', 'Section A').strip(),
                        points=float(row.get('points', 1.0)),
                        difficulty=row.get('difficulty', 'medium').lower(),
                        category=row.get('category', '').strip(),
                        correct_answer=row.get('correct_answer', '').strip()
                    )

                    if q_type == 'mcq':
                        options_str = row.get('options', '')
                        correct_text = row.get('correct_answer', '').strip()
                        if options_str:
                            for opt_text in [o.strip() for o in options_str.split(';') if o.strip()]:
                                Option.objects.create(
                                    question=question, text=opt_text,
                                    is_correct=(opt_text == correct_text)
                                )
                    created_count += 1
                except Exception as e:
                    errors.append(f"Row {row_idx}: {str(e)}")

            return Response({
                "status": "success",
                "message": f"Successfully uploaded {created_count} questions.",
                "errors": errors
            })
        except Exception as e:
            return Response({"error": f"Failed to process CSV: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='bulk-upload/template')
    def bulk_upload_template(self, request):
        """CPT-Integrated: Serves a CSV template for bulk question upload."""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="cpt_question_template.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'section', 'question_text', 'question_type', 'points',
            'difficulty', 'category', 'source_text', 'reference_translation',
            'translation_brief', 'specialization', 'options', 'correct_answer'
        ])
        writer.writerow([
            'Section A', 'Sample MCQ Question?', 'mcq', '1.0',
            'medium', 'General', '', '', '', '',
            'Option 1;Option 2;Option 3', 'Option 1'
        ])
        return response

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Transitions a question to APPROVED status."""
        question = self.get_object()
        is_assigned = ExaminerAssignment.objects.filter(exam=question.exam, user=request.user).exists()
        if not (request.user.is_staff or is_assigned):
            return Response({"error": "Not authorized to approve content for this exam."}, status=403)

        question.status = 'approved'
        question.approved_by = request.user
        question.save()

        AuditLog.objects.create(
            actor=request.user, action='UPDATE', target_model='Question',
            target_object_id=str(question.id),
            details=f"Approved question ID {question.id} for {question.exam.title}"
        )
        return Response({"status": "Question approved"})

    @action(detail=True, methods=['post'])
    def lock(self, request, pk=None):
        """Locks a question to prevent further edits."""
        question = self.get_object()
        if not request.user.is_staff:
            return Response({"error": "Only administrators can lock content."}, status=403)
        question.status = 'locked'
        question.save()
        return Response({"status": "Question locked and ready for exam sitting."})


# ===========================================================================
# CATEGORY VIEWSET
# ===========================================================================
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = ExamCategory.objects.all()
    serializer_class = ExamCategorySerializer
    permission_classes = [permissions.IsAdminUser]


# ===========================================================================
# LANGUAGE PAIR VIEWSET
# ===========================================================================
class LanguagePairViewSet(viewsets.ModelViewSet):
    """
    CPT-Integrated: CRUD for structured translation pairs (e.g., EN-FR).
    Only accessible by Admins.
    """
    queryset = LanguagePair.objects.all()
    serializer_class = LanguagePairSerializer
    permission_classes = [permissions.IsAdminUser]


# ===========================================================================
# BACKUP MANAGEMENT VIEWS
# ===========================================================================
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
            dt_object = datetime.fromtimestamp(stats.st_mtime)
            files.append({
                "filename": f,
                "size": stats.st_size,
                "size_formatted": f"{round(stats.st_size / 1024, 2)} KB",
                "created_at": dt_object.isoformat()
            })

    files.sort(key=lambda x: x['created_at'], reverse=True)
    return Response(files)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_backup_view(request):
    try:
        from scripts.backup_local import run_backup
        run_backup()
        return Response({"status": "success", "message": "System snapshot created successfully."})
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
        call_command('restore_db', filename)
        return Response({"message": "Database successfully restored."})
    except Exception as e:
        return Response({"error": str(e)}, status=500)