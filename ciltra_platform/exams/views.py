from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
import csv
import io

from .models import Exam, Question, Option, ExamCategory
from .serializers import (
    ExamSerializer, 
    ExamDetailSerializer, 
    ExamListSerializer,
    QuestionSerializer, 
    ExamCategorySerializer, 
    OptionSerializer
)
# Ensure you have the permissions file created in the previous step
from users.permissions import IsTeacher, IsStudent, IsAdmin 

class ExamViewSet(viewsets.ModelViewSet):
    # Note: get_queryset() overrides this at runtime; kept for DRF router introspection.
    queryset = Exam.objects.all().order_by('-created_at')
    filter_backends = [filters.SearchFilter]
    search_fields = ['title', 'category__name', 'language_pair__pair_code']

    def get_queryset(self):
        user = self.request.user

        # Staff, teachers, and admins see ALL exams (active or not) for management.
        if user.is_staff or getattr(user, 'role', None) in ('teacher', 'admin'):
            return Exam.objects.all().order_by('-created_at')

        # Students start from only active exams.
        queryset = Exam.objects.filter(is_active=True)

        # ── Language Pair Filtering ───────────────────────────────────────────
        # Priority 1: explicit query param  ?language_pair=<id>
        lp_param = self.request.query_params.get('language_pair')
        if lp_param:
            queryset = queryset.filter(language_pair_id=lp_param)

        # Priority 2: user's profile field  user.selected_language_pair
        elif hasattr(user, 'selected_language_pair') and user.selected_language_pair:
            queryset = queryset.filter(language_pair=user.selected_language_pair)

        # If neither is set, return all active exams (no language-pair restriction yet).
        return queryset.order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ExamDetailSerializer
        if self.action == 'list':
            return ExamListSerializer
        return ExamSerializer

    def get_permissions(self):
        # Admin/Teacher can do everything
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'assign_questions', 'remove_questions']:
            return [IsTeacher()]
        # Public/Students can only view
        return [permissions.IsAuthenticated()]

    @action(detail=True, methods=['post'], url_path='assign-questions')
    def assign_questions(self, request, pk=None):
        exam = self.get_object()
        question_ids = request.data.get('question_ids', [])
        questions = Question.objects.filter(id__in=question_ids)
        for q in questions:
            exam.questions.add(q)
        return Response({"status": "success", "message": f"{questions.count()} questions added"})

    @action(detail=True, methods=['post'], url_path='remove-questions')
    def remove_questions(self, request, pk=None):
        exam = self.get_object()
        question_ids = request.data.get('question_ids', [])
        questions = Question.objects.filter(id__in=question_ids)
        for q in questions:
            exam.questions.remove(q)
        return Response({"status": "success", "message": "Questions removed"})

class QuestionViewSet(viewsets.ModelViewSet):
    queryset = Question.objects.all().order_by('-id')
    serializer_class = QuestionSerializer
    permission_classes = [IsTeacher] # Only teachers/admins
    filter_backends = [filters.SearchFilter]
    search_fields = ['text', 'category']
    parser_classes = (MultiPartParser, FormParser) 

    @action(detail=True, methods=['post'])
    def add_options(self, request, pk=None):
        question = self.get_object()
        options_data = request.data.get('options', [])
        for opt in options_data:
            opt['question'] = question.id
            Option.objects.create(question=question, **opt)
        return Response({"status": "Options added"}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='bulk-upload')
    def bulk_upload(self, request):
        """
        CPT-Integrated: Bulk uploads questions (MCQ or Theory) with full metadata support.
        Expects a CSV file with headers: section, question_text, question_type, points, 
        difficulty, category, source_text, reference_translation, translation_brief, 
        specialization, options (semicolon separated), correct_answer.
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
                    # Basic field extraction
                    question_text = row.get('question_text', '').strip()
                    if not question_text:
                        continue # Skip empty rows

                    q_type = row.get('question_type', 'mcq').lower()
                    
                    # Create the Question record
                    question = Question.objects.create(
                        text=question_text,
                        question_type=q_type,
                        section=row.get('section', 'Section A').strip(),
                        points=float(row.get('points', 1.0)),
                        difficulty=row.get('difficulty', 'medium').lower(),
                        category=row.get('category', '').strip(),
                        source_text=row.get('source_text', '').strip() or None,
                        reference_translation=row.get('reference_translation', '').strip() or None,
                        translation_brief=row.get('translation_brief', '').strip() or None,
                        specialization=row.get('specialization', '').strip() or None,
                        correct_answer=row.get('correct_answer', '').strip()
                    )

                    # Handle MCQ options
                    if q_type == 'mcq':
                        options_str = row.get('options', '')
                        correct_text = row.get('correct_answer', '').strip()
                        
                        if options_str:
                            options_list = [o.strip() for o in options_str.split(';') if o.strip()]
                            for opt_text in options_list:
                                Option.objects.create(
                                    question=question,
                                    text=opt_text,
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

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = ExamCategory.objects.all()
    serializer_class = ExamCategorySerializer
    permission_classes = [IsTeacher]