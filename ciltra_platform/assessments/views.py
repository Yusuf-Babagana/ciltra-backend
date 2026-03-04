from rest_framework import generics, permissions, status, views
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import ExamSession, StudentAnswer
from .serializers import (
    ExamSessionSerializer, 
    StudentAnswerSerializer, 
    ActiveExamSessionSerializer
)

from exams.models import Exam, Question, Option
from exams.serializers import ExamDetailSerializer
from certificates.models import Certificate
from users.permissions import IsTeacher, IsStudent, IsAdmin  # <--- New Permissions

User = get_user_model()

class AdminStatsView(views.APIView):
    """
    Returns aggregated statistics for the Admin Dashboard.
    Only Admins can access this.
    """
    permission_classes = [IsAdmin]

    def get(self, request):
        return Response({
            "total_exams": Exam.objects.count(),
            # Count users who are NOT admins/staff as students
            "total_candidates": User.objects.filter(is_staff=False, role='student').count(),
            # pending_grading = Submitted (end_time set) but NOT graded
            "pending_grading": ExamSession.objects.filter(end_time__isnull=False, is_graded=False).count(),
            "issued_certificates": Certificate.objects.count()
        })


# --- TEACHER / ADMIN VIEWS (Grading) ---

class PendingGradingListView(generics.ListAPIView):
    """List all exam sessions that require manual grading."""
    permission_classes = [IsTeacher] # Teachers & Admins
    serializer_class = ExamSessionSerializer

    def get_queryset(self):
        return ExamSession.objects.filter(end_time__isnull=False, is_graded=False)

class SubmitGradeView(views.APIView):
    """Teacher submits marks for a specific answer."""
    permission_classes = [IsTeacher] # Teachers & Admins

    def post(self, request, session_id):
        session = get_object_or_404(ExamSession, id=session_id)
        
        # Expects a list of { "question_id": 1, "marks": 5, "comment": "Good job" }
        grades = request.data.get('grades', [])
        
        total_score_update = 0
        
        for grade in grades:
            # Find the student's answer for this question in this session
            answer = get_object_or_404(StudentAnswer, session=session, question_id=grade['question_id'])
            
            # Update marks and comment
            answer.awarded_marks = grade['marks']
            answer.grader_comment = grade.get('comment', '')
            answer.save()
            
            # Aggregate score (Note: Logic might need adjustment if re-grading)
            total_score_update += float(grade['marks'])

        # Recalculate total score from scratch to be safe
        # (This is better than += which can bug if graded twice)
        total_score = 0
        for ans in session.answers.all():
            total_score += (ans.awarded_marks or 0)

        session.score = total_score
        session.is_graded = True
        
        # Determine Pass/Fail
        if session.score >= session.exam.pass_mark_percentage:
            session.passed = True
            # Trigger Certificate Generation
            Certificate.objects.get_or_create(session=session)
        else:
            session.passed = False
            
        session.save()
        
        return Response({"status": "Graded successfully", "final_score": session.score})


# --- STUDENT VIEWS (Taking Exams) ---

class StartExamView(views.APIView):
    """
    Student starts an exam. 
    Creates a session and returns the exam details WITH questions.
    """
    permission_classes = [IsStudent]

    def post(self, request, exam_id):
        exam = get_object_or_404(Exam, id=exam_id)
        
        # Check if active session already exists (resume)
        active_session = ExamSession.objects.filter(
            user=request.user, 
            exam=exam, 
            end_time__isnull=True
        ).first()

        if active_session:
            # Resume existing session using the 'Active' serializer (includes questions)
            serializer = ActiveExamSessionSerializer(active_session)
            return Response(serializer.data)

        # Create new session
        session = ExamSession.objects.create(
            user=request.user,
            exam=exam
        )
        
        serializer = ActiveExamSessionSerializer(session)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class SubmitExamView(views.APIView):
    """
    Student submits answers.
    Calculates MCQ score immediately.
    """
    permission_classes = [IsStudent]

    def post(self, request, session_id):
        session = get_object_or_404(ExamSession, id=session_id, user=request.user)
        
        if session.end_time:
            return Response({"error": "Exam already submitted"}, status=status.HTTP_400_BAD_REQUEST)

        answers_data = request.data.get('answers', [])
        
        score = 0
        has_theory = False

        for ans in answers_data:
            question = get_object_or_404(Question, id=ans['question_id'])
            
            # Create the answer record
            student_answer = StudentAnswer.objects.create(
                session=session,
                question=question,
                text_answer=ans.get('text_answer', '')
            )
            
            # Handle MCQ Grading
            # Note: Ensure QuestionType string matches your model choice (case-sensitive)
            if question.question_type.lower() == 'mcq':
                selected_opt_id = ans.get('selected_option_id')
                if selected_opt_id:
                    option = get_object_or_404(Option, id=selected_opt_id)
                    student_answer.selected_option = option
                    
                    if option.is_correct:
                        # Assuming 'points' is the field name on Question model (check your model)
                        points = getattr(question, 'points', 0) or getattr(question, 'marks', 0)
                        score += points
                        student_answer.awarded_marks = points
                    
                    student_answer.save()
            else:
                has_theory = True

        # Finalize Session
        session.end_time = timezone.now()
        session.score = score
        
        # If there are NO theory questions, we can determine Pass/Fail immediately
        if not has_theory:
            session.is_graded = True
            if session.score >= session.exam.pass_mark_percentage:
                session.passed = True
                Certificate.objects.get_or_create(session=session)
            else:
                session.passed = False
        else:
            session.is_graded = False # Needs manual review by Teacher
            
        session.save()
        
        return Response({
            "status": "Submitted", 
            "score": score, 
            "is_graded": session.is_graded
        })

class StudentExamAttemptsView(generics.ListAPIView):
    """List all exam sessions for the logged-in student (Lightweight)."""
    permission_classes = [IsStudent]
    serializer_class = ExamSessionSerializer

    def get_queryset(self):
        return ExamSession.objects.filter(user=self.request.user).order_by('-start_time')

class ExamSessionDetailView(generics.RetrieveAPIView):
    """
    Allow student to retrieve a specific session details.
    Uses Active serializer so they can see questions if resuming.
    """
    permission_classes = [permissions.IsAuthenticated] # Students or Teachers checking details
    serializer_class = ActiveExamSessionSerializer 
    
    def get_queryset(self):
        # Users can only see their own sessions
        return ExamSession.objects.filter(user=self.request.user)

    def get_object(self):
        return get_object_or_404(ExamSession, id=self.kwargs['pk'], user=self.request.user)