# assessments/views.py

from rest_framework import generics, permissions, status, views
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.contrib.auth import get_user_model

# --- ANALYTICS IMPORTS ---
from django.db.models import Sum, Count, Avg
from django.db.models.functions import TruncMonth

# --- Models ---
from .models import ExamSession, StudentAnswer
from exams.models import Exam, Question, Option
from payments.models import Payment 
from certificates.models import Certificate

# --- Serializers ---
from .serializers import (
    ExamSessionSerializer, 
    StudentAnswerSerializer, 
    ActiveExamSessionSerializer
)
from exams.serializers import (
    ExamDetailSerializer, 
    ExamSessionStartSerializer, 
    ExamSubmitSerializer
)

User = get_user_model()

# ==========================================
#              ADMIN VIEWS
# ==========================================

class AdminStatsView(views.APIView):
    """
    Returns aggregated statistics for the Admin Dashboard.
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        # Count all users who are NOT staff/admin as candidates
        candidate_count = User.objects.filter(is_staff=False).count()

        return Response({
            "total_exams": Exam.objects.count(),
            "total_candidates": candidate_count,
            "pending_grading": ExamSession.objects.filter(end_time__isnull=False, is_graded=False).count(),
            "issued_certificates": Certificate.objects.count()
        })

class PendingGradingListView(generics.ListAPIView):
    """List all exam sessions that require manual grading."""
    permission_classes = [permissions.IsAuthenticated] 
    serializer_class = ExamSessionSerializer

    def get_queryset(self):
        return ExamSession.objects.filter(end_time__isnull=False, is_graded=False)

class SubmitGradeView(views.APIView):
    """
    Admin submits marks for manual questions (Translation/Theory).
    Re-calculates the final percentage after grading.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, session_id):
        session = get_object_or_404(ExamSession, id=session_id)
        
        grades = request.data.get('grades', []) # Expects: [{ "question_id": 1, "marks": 8 }]
        
        # 1. Update the specific answers with new marks
        for grade in grades:
            answer = get_object_or_404(StudentAnswer, session=session, question_id=grade['question_id'])
            
            # Validation: Don't give 15 marks for a 10-mark question
            max_points = answer.question.points
            awarded = float(grade['marks'])
            
            if awarded > max_points:
                return Response(
                    {"error": f"Cannot award {awarded} marks for Q{answer.question.id}. Max is {max_points}."}, 
                    status=400
                )

            answer.awarded_marks = awarded
            answer.grader_comment = grade.get('comment', '')
            answer.save()

        # 2. RE-CALCULATE TOTAL SCORE (Hybrid Logic)
        # Calculate Total Possible Points for the Exam
        total_possible = session.exam.questions.aggregate(total=Sum('points'))['total'] or 0
        
        # Calculate Total Earned Points (MCQ + Manual)
        total_earned = StudentAnswer.objects.filter(session=session).aggregate(total=Sum('awarded_marks'))['total'] or 0

        # Calculate Percentage
        if total_possible > 0:
            final_percentage = (total_earned / total_possible) * 100
        else:
            final_percentage = 0

        # 3. Update Session Status
        session.score = final_percentage
        session.is_graded = True # Marking complete
        
        # Determine Pass/Fail
        pass_mark = getattr(session.exam, 'passing_score', getattr(session.exam, 'pass_mark_percentage', 50))
        
        if session.score >= pass_mark:
            session.passed = True
            Certificate.objects.get_or_create(session=session)
        else:
            session.passed = False
            
        session.save()
        
        return Response({
            "status": "Graded successfully", 
            "final_score": session.score,
            "passed": session.passed
        })


# ==========================================
#              STUDENT VIEWS
# ==========================================

class StartExamView(views.APIView):
    """
    Student starts an exam. 
    Creates a session and returns the exam details WITH questions.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, exam_id):
        exam = get_object_or_404(Exam, id=exam_id)
        
        # 1. Payment Check (Security)
        if not exam.is_free:
            has_paid = Payment.objects.filter(
                user=request.user, 
                exam=exam, 
                status='success'
            ).exists()

            if not has_paid:
                 return Response(
                     {"error": "Payment Required", "detail": "You must pay for this exam before starting."}, 
                     status=status.HTTP_402_PAYMENT_REQUIRED
                 )

        # 2. Check or Create Session
        session, created = ExamSession.objects.get_or_create(
            user=request.user, 
            exam=exam, 
            end_time__isnull=True,
            defaults={'start_time': timezone.now()}
        )

        # 3. Use the START serializer (Includes Questions)
        serializer = ExamSessionStartSerializer(session)
        return Response(serializer.data)


class SubmitExamView(views.APIView):
    """
    Student submits answers.
    - MCQs are auto-graded immediately based on 'points'.
    - Theory/Translation questions are saved as 0 marks.
    - Final score is calculated as a PERCENTAGE.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, session_id):
        session = get_object_or_404(ExamSession, id=session_id, user=request.user)
        
        if session.end_time:
            return Response({"error": "Exam already submitted"}, status=status.HTTP_400_BAD_REQUEST)

        answers_data = request.data.get('answers', [])
        
        total_earned_points = 0
        has_manual_questions = False
        
        # We need to know the total possible points to calculate percentage
        # Fetch all questions for this exam to calculate the denominator
        all_questions = session.exam.questions.all()
        total_possible_points = sum(q.points for q in all_questions)

        for ans in answers_data:
            # Validate question belongs to this exam? (Optional but good security)
            try:
                question = all_questions.get(id=ans['question_id'])
            except Question.DoesNotExist:
                continue # Skip invalid questions

            # Create Answer Record
            student_answer, created = StudentAnswer.objects.get_or_create(
                session=session,
                question=question,
                defaults={'text_answer': ans.get('text_answer', '')}
            )
            
            # --- LOGIC 1: MCQ (Auto-Grade) ---
            if question.question_type == Question.QuestionType.MCQ:
                selected_opt_id = ans.get('answer') or ans.get('selected_option_id')
                if selected_opt_id:
                    try:
                        option = Option.objects.get(id=int(selected_opt_id))
                        student_answer.selected_option = option
                        
                        if option.is_correct:
                            points = question.points
                            student_answer.awarded_marks = points
                            total_earned_points += points
                        else:
                            student_answer.awarded_marks = 0
                        
                        student_answer.save()
                    except (Option.DoesNotExist, ValueError):
                        pass 
            
            # --- LOGIC 2: THEORY (Manual) ---
            else:
                has_manual_questions = True
                student_answer.awarded_marks = 0 # Waiting for admin
                student_answer.text_answer = ans.get('text_answer', '')
                student_answer.save()

        # Finalize Session
        session.end_time = timezone.now()
        
        # Calculate Percentage Score
        if total_possible_points > 0:
            percentage_score = (total_earned_points / total_possible_points) * 100
        else:
            percentage_score = 0
            
        session.score = percentage_score
        
        # Determine Status
        if has_manual_questions:
            session.is_graded = False # Needs Admin Review
            session.passed = False    # Can't pass until graded
        else:
            session.is_graded = True
            pass_mark = getattr(session.exam, 'passing_score', getattr(session.exam, 'pass_mark_percentage', 50))
            if session.score >= pass_mark:
                session.passed = True
                Certificate.objects.get_or_create(session=session)
            else:
                session.passed = False
            
        session.save()
        
        return Response({
            "status": "Submitted", 
            "score": session.score, 
            "is_graded": session.is_graded,
            "message": "Exam submitted for grading." if has_manual_questions else "Exam completed."
        })


class ResultView(views.APIView):
    """
    Returns the final result of an exam session.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, session_id):
        session = get_object_or_404(ExamSession, id=session_id, user=request.user)
        
        if not session.end_time:
            return Response({"error": "Exam not yet submitted"}, status=400)

        pass_mark = getattr(session.exam, 'passing_score', getattr(session.exam, 'pass_mark_percentage', 50))

        return Response({
            "exam_title": session.exam.title,
            "score": session.score,
            "passing_score": pass_mark,
            "is_passed": session.passed,
            "is_graded": session.is_graded,
            "certificate_id": getattr(session, 'certificate', None) and session.certificate.id
        })


class StudentExamAttemptsView(generics.ListAPIView):
    """List all exam sessions for the logged-in student."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ExamSessionSerializer

    def get_queryset(self):
        return ExamSession.objects.filter(user=self.request.user).order_by('-start_time')


class ExamSessionDetailView(generics.RetrieveAPIView):
    """
    Allow student to retrieve a specific session details.
    Uses StartSerializer to ensure QUESTIONS are sent when resuming/refreshing.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ExamSessionStartSerializer 
    
    def get_queryset(self):
        return ExamSession.objects.all()

    def get_object(self):
        return get_object_or_404(ExamSession, id=self.kwargs['pk'], user=self.request.user)
        
# --- GetSessionView is required for the frontend hook ---
class GetSessionView(views.APIView):
    """
    Retrieves an active session.
    Used by the frontend to load questions when entering the Exam Room.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, session_id):
        session = get_object_or_404(ExamSession, id=session_id, user=request.user)
        serializer = ExamSessionStartSerializer(session)
        return Response(serializer.data)


# ==========================================
#              EXAMINER VIEWS
# ==========================================

class GradingSessionDetailView(views.APIView):
    """
    Retrieve full session details for an Examiner/Admin.
    """
    permission_classes = [permissions.IsAuthenticated] 

    def get(self, request, pk):
        session = get_object_or_404(ExamSession, id=pk)
        
        # Security check
        if hasattr(request.user, 'role') and request.user.role == 'candidate' and not request.user.is_staff:
             return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        # 1. Answers
        answers = StudentAnswer.objects.filter(session=session)
        answers_data = []
        for ans in answers:
            answers_data.append({
                "question": ans.question.id,
                "text_answer": ans.text_answer,
                "selected_option": {"text": ans.selected_option.text} if ans.selected_option else None,
                "awarded_marks": ans.awarded_marks
            })

        # 2. Questions (With Correct Answers)
        questions = session.exam.questions.all().order_by('id')
        questions_data = []
        for q in questions:
            opts = q.options.all()
            questions_data.append({
                "id": q.id,
                "text": q.text,
                "question_type": q.question_type,
                "points": q.points,
                "correct_answer": q.correct_answer, 
                "options": [{"id": o.id, "text": o.text, "is_correct": o.is_correct} for o in opts]
            })

        # 3. Response
        pass_mark = getattr(session.exam, 'passing_score', getattr(session.exam, 'pass_mark_percentage', 50))
        
        data = {
            "id": session.id,
            "exam": {
                "title": session.exam.title,
                "pass_mark_percentage": pass_mark
            },
            "user": {
                "id": session.user.id,
                "first_name": session.user.first_name,
                "last_name": session.user.last_name,
                "email": session.user.email
            },
            "questions": questions_data,
            "answers": answers_data,
            "score": session.score,
            "passed": session.passed,
            "end_time": session.end_time
        }
        return Response(data)


class ExaminerStatsView(views.APIView):
    """Returns statistics for the Examiner Dashboard."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        pending_count = ExamSession.objects.filter(end_time__isnull=False, is_graded=False).count()
        graded_count = ExamSession.objects.filter(is_graded=True).count()
        return Response({
            "pending": pending_count,
            "graded": graded_count,
            "total": pending_count + graded_count
        })

class GradedHistoryListView(generics.ListAPIView):
    """List all exam sessions that have been graded."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ExamSessionSerializer

    def get_queryset(self):
        return ExamSession.objects.filter(is_graded=True).order_by('-end_time')


class AdminAnalyticsView(views.APIView):
    """
    Returns aggregated data for Admin Reports:
    1. Monthly Registrations (Line Chart)
    2. Pass vs Fail Ratio (Pie Chart)
    3. Average Score per Exam (Bar Chart)
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        # 1. Monthly User Registrations (Last 12 Months)
        monthly_users = User.objects.filter(role='student')\
            .annotate(month=TruncMonth('date_joined'))\
            .values('month')\
            .annotate(count=Count('id'))\
            .order_by('month')

        registration_data = [
            {
                "name": item['month'].strftime('%b'), # Jan, Feb, etc.
                "students": item['count']
            } 
            for item in monthly_users
        ]

        # 2. Pass vs Fail Ratio
        # Assuming 50% is the generic pass mark for aggregation
        sessions = ExamSession.objects.filter(end_time__isnull=False)
        pass_count = sessions.filter(score__gte=50).count()
        fail_count = sessions.filter(score__lt=50).count()

        pass_fail_data = [
            {"name": "Passed", "value": pass_count, "fill": "#22c55e"}, # Green
            {"name": "Failed", "value": fail_count, "fill": "#ef4444"}, # Red
        ]

        # 3. Average Score per Exam (Top 5 Active Exams)
        exam_performance = ExamSession.objects.values('exam__title')\
            .annotate(avg_score=Avg('score'))\
            .order_by('-avg_score')[:5]

        performance_data = [
            {
                "name": item['exam__title'][:15] + "...", # Truncate long names
                "score": round(item['avg_score'], 1)
            }
            for item in exam_performance
        ]

        return Response({
            "registrations": registration_data,
            "pass_fail": pass_fail_data,
            "performance": performance_data
        })