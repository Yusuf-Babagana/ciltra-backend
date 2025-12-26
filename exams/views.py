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
from rest_framework.parsers import MultiPartParser, FormParser

class ExamViewSet(viewsets.ModelViewSet):
    queryset = Exam.objects.all().order_by('-created_at')
    
    # Enable search on title and category name
    filter_backends = [filters.SearchFilter]
    search_fields = ['title', 'category__name']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ExamDetailSerializer
        if self.action == 'list':
            # Admin gets full info, Candidate gets simple list
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

    @action(detail=False, methods=['post'], url_path='submit/(?P<session_id>[^/.]+)')
    def submit_exam_session(self, request, session_id=None):
        # Logic for grading would go here (simplified for now)
        return Response({"status": "submitted"})
    

    # --- ADD THIS NEW ACTION ---
    @action(detail=True, methods=['post'], url_path='assign-questions')
    def assign_questions(self, request, pk=None):
        """
        Assigns a list of Question IDs to this Exam.
        Payload: { "question_ids": [1, 2, 3] }
        """
        exam = self.get_object()
        question_ids = request.data.get('question_ids', [])
        
        # Update the questions to point to this exam
        count = Question.objects.filter(id__in=question_ids).update(exam=exam)
        
        return Response({"status": f"Added {count} questions to {exam.title}"})

    @action(detail=True, methods=['post'], url_path='remove-questions')
    def remove_questions(self, request, pk=None):
        """
        Removes questions from the exam (sets exam=None), returning them to the bank.
        """
        question_ids = request.data.get('question_ids', [])
        Question.objects.filter(id__in=question_ids, exam=self.get_object()).update(exam=None)
        return Response({"status": "Questions returned to bank"})

    @action(detail=False, methods=['post'], url_path='submit/(?P<session_id>[^/.]+)')
    def submit_exam_session(self, request, session_id=None):
        """
        Receives answers from the student and saves them.
        Payload: { "answers": [ { "question_id": 1, "answer": "A" }, ... ] }
        """
        try:
            session = ExamSession.objects.get(id=session_id, user=request.user)
        except ExamSession.DoesNotExist:
            return Response({"error": "Session not found"}, status=status.HTTP_404_NOT_FOUND)

        if session.end_time:
             return Response({"error": "Exam already submitted"}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Save Answers
        answers_data = request.data.get('answers', [])
        score = 0
        
        for ans in answers_data:
            q_id = ans.get('question_id')
            user_response = ans.get('answer')
            
            question = Question.objects.get(id=q_id)
            
            # Basic Auto-Grading for MCQ
            is_correct = False
            if question.question_type == 'mcq':
                # Check against Option table
                correct_option = Option.objects.filter(question=question, is_correct=True).first()
                if correct_option and user_response.lower() == correct_option.text.lower():
                    is_correct = True
                    score += question.points
            
            # Save the record
            StudentAnswer.objects.create(
                session=session,
                question=question,
                text_answer=user_response,
                is_correct=is_correct,
                score_awarded=question.points if is_correct else 0
            )

        # 2. Finalize Session
        session.score = score
        session.end_time = timezone.now()
        session.is_graded = True # Set to False if you have Essay questions needing manual review
        session.save()

        return Response({"status": "Exam submitted successfully", "score": score})


    


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

    # Add parsers to handle file uploads
    parser_classes = (MultiPartParser, FormParser) 

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
                    # --- FIX: Changed 'marks' to 'points' to match your Model ---
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