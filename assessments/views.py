from rest_framework import generics, permissions, status, views
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import ExamSession, StudentAnswer
from .serializers import ExamSessionSerializer, StudentAnswerSerializer, ActiveExamSessionSerializer

from exams.models import Exam, Question, Option
from exams.serializers import ExamDetailSerializer
from django.contrib.auth import get_user_model
from exams.models import Exam
from certificates.models import Certificate
# ExamSession is already imported in this file

User = get_user_model()

class AdminStatsView(views.APIView):
    """
    Returns aggregated statistics for the Admin Dashboard.
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        return Response({
            "total_exams": Exam.objects.count(),
            # Count users who are NOT admins/staff as candidates
            "total_candidates": User.objects.filter(is_staff=False).count(),
            # pending_grading = Submitted (end_time set) but NOT graded
            "pending_grading": ExamSession.objects.filter(end_time__isnull=False, is_graded=False).count(),
            "issued_certificates": Certificate.objects.count()
        })


# --- ADMIN VIEWS ---

class PendingGradingListView(generics.ListAPIView):
    """List all exam sessions that require manual grading."""
    permission_classes = [permissions.IsAdminUser]
    serializer_class = ExamSessionSerializer

    def get_queryset(self):
        return ExamSession.objects.filter(end_time__isnull=False, is_graded=False)

class SubmitGradeView(views.APIView):
    """Admin submits marks for a specific answer."""
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, session_id):
        session = get_object_or_404(ExamSession, id=session_id)
        
        # Expects a list of { "question_id": 1, "marks": 5 }
        grades = request.data.get('grades', [])
        
        total_score_update = 0
        
        for grade in grades:
            answer = get_object_or_404(StudentAnswer, session=session, question_id=grade['question_id'])
            answer.awarded_marks = grade['marks']
            answer.grader_comment = grade.get('comment', '')
            answer.save()
            total_score_update += float(grade['marks'])

        # Update Session Status
        session.score = (session.score or 0) + total_score_update
        session.is_graded = True
        
        # Determine Pass/Fail
        if session.score >= session.exam.pass_mark_percentage:
            session.passed = True
            # Trigger Certificate Generation
            from certificates.models import Certificate
            Certificate.objects.get_or_create(session=session)
            
        session.save()
        
        return Response({"status": "Graded successfully", "final_score": session.score})


# --- STUDENT VIEWS ---

class StartExamView(views.APIView):
    """
    Student starts an exam. 
    Creates a session and returns the exam details WITH questions.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, exam_id):
        exam = get_object_or_404(Exam, id=exam_id)
        
        # Check if active session already exists
        active_session = ExamSession.objects.filter(
            user=request.user, 
            exam=exam, 
            end_time__isnull=True
        ).first()

        if active_session:
            # Resume existing session
            serializer = ExamSessionSerializer(active_session)
            data = serializer.data
            # Inject questions manually since SessionSerializer might not have them
            data['exam'] = ExamDetailSerializer(exam).data 
            return Response(data)

        # Create new session
        session = ExamSession.objects.create(
            user=request.user,
            exam=exam
        )
        
        serializer = ExamSessionSerializer(session)
        data = serializer.data
        data['exam'] = ExamDetailSerializer(exam).data 
        
        return Response(data, status=status.HTTP_201_CREATED)


class SubmitExamView(views.APIView):
    """
    Student submits answers.
    Calculates MCQ score immediately.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, session_id):
        session = get_object_or_404(ExamSession, id=session_id, user=request.user)
        
        if session.end_time:
            return Response({"error": "Exam already submitted"}, status=status.HTTP_400_BAD_REQUEST)

        answers_data = request.data.get('answers', [])
        
        score = 0
        has_theory = False

        for ans in answers_data:
            question = get_object_or_404(Question, id=ans['question_id'])
            
            # Save the answer
            student_answer = StudentAnswer.objects.create(
                session=session,
                question=question,
                text_answer=ans.get('text_answer', '')
            )
            
            # Handle MCQ Grading
            if question.question_type == Question.QuestionType.MCQ:
                selected_opt_id = ans.get('selected_option_id')
                if selected_opt_id:
                    option = get_object_or_404(Option, id=selected_opt_id)
                    student_answer.selected_option = option
                    if option.is_correct:
                        score += question.marks
                        student_answer.awarded_marks = question.marks
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
                # Generate Certificate
                from certificates.models import Certificate
                Certificate.objects.get_or_create(session=session)
            else:
                session.passed = False
        else:
            session.is_graded = False # Needs manual review
            
        session.save()
        
        return Response({
            "status": "Submitted", 
            "score": score, 
            "is_graded": session.is_graded
        })

class StudentExamAttemptsView(generics.ListAPIView):
    """List all exam sessions for the logged-in student (Lightweight)."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ExamSessionSerializer

    def get_queryset(self):
        return ExamSession.objects.filter(user=self.request.user).order_by('-start_time')

class ExamSessionDetailView(generics.RetrieveAPIView):
    """Allow student to retrieve a specific session details (Heavy - Includes Questions)."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ActiveExamSessionSerializer # <--- Use the Active serializer here
    
    def get_queryset(self):
        return ExamSession.objects.all()

    def get_object(self):
        return get_object_or_404(ExamSession, id=self.kwargs['pk'], user=self.request.user)


