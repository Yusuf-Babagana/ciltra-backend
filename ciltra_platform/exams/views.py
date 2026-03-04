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
    queryset = Exam.objects.all().order_by('-created_at')
    filter_backends = [filters.SearchFilter]
    search_fields = ['title', 'category__name']

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
        file_obj = request.FILES.get('file')
        if not file_obj: return Response({"error": "No file"}, status=400)
        try:
            decoded_file = file_obj.read().decode('utf-8')
            reader = csv.DictReader(io.StringIO(decoded_file))
            count = 0
            for row in reader:
                q = Question.objects.create(
                    text=row['question_text'], 
                    question_type=row.get('question_type','mcq').lower(),
                    points=int(row.get('points', 1))
                )
                if q.question_type == 'mcq':
                    correct = row.get('correct_answer','').strip().lower()
                    for opt in row.get('options','').split('|'):
                        Option.objects.create(question=q, text=opt.strip(), is_correct=(opt.strip().lower()==correct))
                count += 1
            return Response({"status": f"Uploaded {count} questions"})
        except Exception as e:
            return Response({"error": str(e)}, status=400)

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = ExamCategory.objects.all()
    serializer_class = ExamCategorySerializer
    permission_classes = [IsTeacher]