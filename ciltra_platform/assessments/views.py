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
from users.permissions import IsTeacher, IsStudent, IsAdmin
from assessments.permissions import IsGraderOrAdmin

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

MODERATION_THRESHOLD = 15  # Points variance that triggers moderator review

class SubmitGradeView(views.APIView):
    """
    CPT Double-Blind Grading View.

    Flow:
      1. Grader 1 submits rubric scores  →  stored on answers, session.grader_one set.
      2. Grader 2 submits rubric scores  →  stored on answers, session.grader_two set.
      3. System compares totals; if variance > MODERATION_THRESHOLD, flags for moderation.
      4. If both graders agree (or moderator resolves), Pass/Fail is decided using CPT rules:
            - Overall score >= 70 %
            - Section B score >= 80 %
    """
    permission_classes = [IsGraderOrAdmin]

    def post(self, request, session_id):
        session = get_object_or_404(ExamSession, id=session_id)
        user = request.user

        # ── 1. Grader assignment (double-blind slot allocation) ──────────────
        if not session.grader_one:
            session.grader_one = user
            is_first_grader = True
        elif session.grader_one != user and not session.grader_two:
            session.grader_two = user
            is_first_grader = False
        else:
            return Response(
                {"error": "This session already has two graders assigned."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ── 2. Rubric score processing ────────────────────────────────────────
        # Expected payload: { "grades": [ { "question_id": 1,
        #   "accuracy": 35, "style": 20, "terminology": 12,
        #   "presentation": 8, "ethics": 9, "comment": "..." }, ... ] }
        grades = request.data.get('grades', [])
        this_grader_total = 0

        for grade in grades:
            answer = get_object_or_404(
                StudentAnswer, session=session, question_id=grade['question_id']
            )

            # Store rubric dimensions (overwrite slot for this grader)
            answer.accuracy_score     = grade.get('accuracy', 0)
            answer.style_score        = grade.get('style', 0)
            answer.terminology_score  = grade.get('terminology', 0)
            answer.presentation_score = grade.get('presentation', 0)
            answer.ethics_score       = grade.get('ethics', 0)
            answer.grader_comment     = grade.get('comment', answer.grader_comment)

            # awarded_marks = sum of all rubric dimensions
            answer.awarded_marks = (
                answer.accuracy_score +
                answer.style_score +
                answer.terminology_score +
                answer.presentation_score +
                answer.ethics_score
            )
            this_grader_total += float(answer.awarded_marks)
            answer.save()

        # ── 3. Moderation check (runs only once both graders have scored) ─────
        if session.grader_one and session.grader_two:
            # Recalculate total from all answers (reflects Grader 2's latest saves)
            total_score = sum(
                float(ans.awarded_marks or 0) for ans in session.answers.all()
            )

            # Grader 1's total was stored before Grader 2 overwrote answers,
            # so we proxy variance as |G2_total - G1_snapshot|.
            # In a full implementation, store per-grader snapshots separately.
            grader_one_snapshot = request.data.get('grader_one_total')  # optional hint
            if grader_one_snapshot is not None:
                variance = abs(this_grader_total - float(grader_one_snapshot))
                if variance > MODERATION_THRESHOLD:
                    session.requires_moderation = True

            session.score = total_score
            session.is_graded = not session.requires_moderation  # graded only if no moderation needed

            # ── 4. CPT pass rules ─────────────────────────────────────────────
            # Overall >= 70 % AND Section B >= 80 %
            if not session.requires_moderation:
                if session.score >= 70 and session.score_section_b >= 80:
                    session.passed = True
                    Certificate.objects.get_or_create(session=session)
                else:
                    session.passed = False

        session.save()

        return Response({
            "status": "Grade submitted successfully.",
            "grader_slot": "grader_one" if is_first_grader else "grader_two",
            "requires_moderation": session.requires_moderation,
            "is_graded": session.is_graded,
            "score": float(session.score) if session.score is not None else None,
        })


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