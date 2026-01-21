import random
import json
import logging
import io 
import openpyxl

from rest_framework import generics, permissions, status, views
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.contrib.auth import get_user_model

# --- ANALYTICS IMPORTS ---
from django.db.models import Sum, Count, Avg
from django.db.models.functions import TruncMonth
from django.http import HttpResponse, FileResponse 

# ReportLab for PDF generation
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors

# --- Models ---
from .models import ExamSession, StudentAnswer
from exams.models import Exam, Question, Option
from payments.models import Payment 
from certificates.models import Certificate
from cores.models import AuditLog

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

from .permissions import IsGraderOrAdmin 

User = get_user_model()
logger = logging.getLogger(__name__)

# ==========================================
#               ADMIN VIEWS
# ==========================================

class AdminStatsView(views.APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        candidate_count = User.objects.filter(is_staff=False).count()
        return Response({
            "total_exams": Exam.objects.count(),
            "total_candidates": candidate_count,
            "pending_grading": ExamSession.objects.filter(end_time__isnull=False, is_graded=False).count(),
            "issued_certificates": Certificate.objects.count()
        })

class PendingGradingListView(generics.ListAPIView):
    """List all exam sessions that require manual grading."""
    permission_classes = [IsGraderOrAdmin] 
    serializer_class = ExamSessionSerializer

    def get_queryset(self):
        return ExamSession.objects.filter(end_time__isnull=False, is_graded=False)

class SubmitGradeView(views.APIView):
    """
    Admin/Grader submits marks for manual questions.
    """
    permission_classes = [IsGraderOrAdmin]

    def post(self, request, session_id):
        session = get_object_or_404(ExamSession, id=session_id)
        
        grades = request.data.get('grades', []) 
        
        for grade in grades:
            answer = get_object_or_404(StudentAnswer, session=session, question_id=grade['question_id'])
            
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

        # RE-CALCULATE TOTAL SCORE
        total_possible = session.exam.questions.aggregate(total=Sum('points'))['total'] or 0
        total_earned = StudentAnswer.objects.filter(session=session).aggregate(total=Sum('awarded_marks'))['total'] or 0

        # --- FIX: Cast to float to avoid Decimal vs Float error ---
        if total_possible > 0:
            final_percentage = (float(total_earned) / float(total_possible)) * 100
        else:
            final_percentage = 0

        session.score = final_percentage
        session.is_graded = True 
        
        pass_mark = getattr(session.exam, 'passing_score', getattr(session.exam, 'pass_mark_percentage', 50))
        
        if session.score >= pass_mark:
            session.passed = True
            Certificate.objects.get_or_create(session=session)
        else:
            session.passed = False
            
        session.save()
        
        # --- AUDIT LOG ---
        AuditLog.objects.create(
            actor=request.user,
            action='GRADE',
            target_model='ExamSession',
            target_object_id=str(session.id),
            details=f"Graded session #{session.id}. Final Score: {session.score}%"
        )
        
        return Response({
            "status": "Graded successfully", 
            "final_score": session.score,
            "passed": session.passed
        })


# ==========================================
#               STUDENT VIEWS
# ==========================================

class StartExamView(views.APIView):
    """
    Starts an exam session. 
    Implements Randomization: Shuffles questions and creates placeholder answers.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, exam_id):
        exam = get_object_or_404(Exam, id=exam_id)
        
        # 1. Payment Check
        if exam.price > 0:
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

        # 2. Create Session
        session, created = ExamSession.objects.get_or_create(
            user=request.user, 
            exam=exam, 
            end_time__isnull=True,
            defaults={'start_time': timezone.now()}
        )

        # 3. RANDOMIZATION LOGIC
        if not session.answers.exists():
            questions = list(exam.questions.all())
            
            if getattr(exam, 'randomize_questions', False):
                random.shuffle(questions)
            
            StudentAnswer.objects.bulk_create([
                StudentAnswer(session=session, question=q) for q in questions
            ])

        serializer = ExamSessionStartSerializer(session)
        return Response(serializer.data)


class SubmitExamView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, session_id):
        session = get_object_or_404(ExamSession, id=session_id, user=request.user)
        
        if session.end_time:
            return Response({"error": "Exam already submitted"}, status=status.HTTP_400_BAD_REQUEST)

        answers_data = request.data.get('answers', [])

        if isinstance(answers_data, dict) and 'answers' in answers_data:
            answers_data = answers_data['answers']

        if isinstance(answers_data, str):
            try:
                answers_data = json.loads(answers_data)
            except json.JSONDecodeError as e:
                return Response({"error": "Invalid JSON format in answers"}, status=400)

        if not isinstance(answers_data, list):
            return Response({"error": "Invalid format. Expected a list of answers."}, status=400)

        has_manual_questions = False
        
        for ans in answers_data:
            if not isinstance(ans, dict): continue

            q_id = ans.get('question_id')
            if not q_id: continue

            student_answer, created = StudentAnswer.objects.get_or_create(
                session=session,
                question_id=q_id
            )
            
            question = student_answer.question 

            if question.question_type == Question.QuestionType.MCQ:
                selected_opt_id = ans.get('answer') or ans.get('selected_option_id')
                if selected_opt_id:
                    try:
                        option = Option.objects.get(id=int(selected_opt_id))
                        student_answer.selected_option = option
                        if option.is_correct:
                            student_answer.awarded_marks = question.points
                        else:
                            student_answer.awarded_marks = 0
                        student_answer.save()
                    except (Option.DoesNotExist, ValueError, TypeError):
                        pass 
            
            else:
                has_manual_questions = True
                student_answer.awarded_marks = 0 
                student_answer.text_answer = ans.get('text_answer', '')
                student_answer.save()

        session.end_time = timezone.now()
        
        total_earned = StudentAnswer.objects.filter(session=session).aggregate(sum=Sum('awarded_marks'))['sum'] or 0
        total_possible = session.exam.questions.aggregate(sum=Sum('points'))['sum'] or 0
        
        if total_possible > 0:
            session.score = (total_earned / total_possible) * 100
        else:
            session.score = 0
            
        if has_manual_questions:
            session.is_graded = False 
            session.passed = False    
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
            "message": "Exam completed."
        })


class ResultView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, session_id):
        session = get_object_or_404(ExamSession, id=session_id, user=request.user)
        
        if not session.end_time:
            return Response({"error": "Exam not yet submitted"}, status=400)

        pass_mark = getattr(session.exam, 'passing_score', getattr(session.exam, 'pass_mark_percentage', 50))
        
        cert_id = None
        if hasattr(session, 'certificate') and session.certificate:
             cert_id = session.certificate.certificate_code 

        return Response({
            "exam_title": session.exam.title,
            "score": session.score,
            "passing_score": pass_mark,
            "is_passed": session.passed,
            "is_graded": session.is_graded,
            "certificate_id": session.id 
        })


class StudentExamAttemptsView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ExamSessionSerializer

    def get_queryset(self):
        return ExamSession.objects.filter(user=self.request.user).order_by('-start_time')


class ExamSessionDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ExamSessionStartSerializer 
    
    def get_queryset(self):
        return ExamSession.objects.all()

    def get_object(self):
        return get_object_or_404(ExamSession, id=self.kwargs['pk'], user=self.request.user)
        
class GetSessionView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, session_id):
        session = get_object_or_404(ExamSession, id=session_id, user=request.user)
        serializer = ExamSessionStartSerializer(session)
        return Response(serializer.data)


# ==========================================
#               EXAMINER/GRADER VIEWS
# ==========================================

class GradingSessionDetailView(views.APIView):
    permission_classes = [IsGraderOrAdmin] 

    def get(self, request, pk):
        session = get_object_or_404(ExamSession, id=pk)
        
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

        # 2. Questions
        questions = session.exam.questions.all().order_by('id')
        questions_data = []
        for q in questions:
            opts = q.options.all()
            
            # Use Options to find correct text since q.correct_answer is gone
            correct_opts = [o.text for o in opts if o.is_correct]
            correct_answer_text = correct_opts[0] if correct_opts else "N/A"

            questions_data.append({
                "id": q.id,
                "text": q.text,
                "question_type": q.question_type,
                "points": q.points,
                "correct_answer": correct_answer_text,
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
    permission_classes = [IsGraderOrAdmin]

    def get(self, request):
        pending_count = ExamSession.objects.filter(end_time__isnull=False, is_graded=False).count()
        graded_count = ExamSession.objects.filter(is_graded=True).count()
        return Response({
            "pending": pending_count,
            "graded": graded_count,
            "total": pending_count + graded_count
        })

class GradedHistoryListView(generics.ListAPIView):
    permission_classes = [IsGraderOrAdmin]
    serializer_class = ExamSessionSerializer

    def get_queryset(self):
        return ExamSession.objects.filter(is_graded=True).order_by('-end_time')


class AdminAnalyticsView(views.APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        monthly_users = User.objects.filter(role='student')\
            .annotate(month=TruncMonth('date_joined'))\
            .values('month')\
            .annotate(count=Count('id'))\
            .order_by('month')

        registration_data = [
            {
                "name": item['month'].strftime('%b'),
                "students": item['count']
            } 
            for item in monthly_users
        ]

        sessions = ExamSession.objects.filter(end_time__isnull=False)
        pass_count = sessions.filter(score__gte=50).count()
        fail_count = sessions.filter(score__lt=50).count()

        pass_fail_data = [
            {"name": "Passed", "value": pass_count, "fill": "#22c55e"}, 
            {"name": "Failed", "value": fail_count, "fill": "#ef4444"}, 
        ]

        exam_performance = ExamSession.objects.values('exam__title')\
            .annotate(avg_score=Avg('score'))\
            .order_by('-avg_score')[:5]

        performance_data = [
            {
                "name": item['exam__title'][:15] + "...", 
                "score": round(item['avg_score'], 1)
            }
            for item in exam_performance
        ]

        return Response({
            "registrations": registration_data,
            "pass_fail": pass_fail_data,
            "performance": performance_data
        })


class ResetSessionView(views.APIView):
    """
    Admin Only: Deletes a session so the student can retake the exam.
    """
    permission_classes = [permissions.IsAdminUser] # Ensure permissions imported

    def delete(self, request, session_id):
        session = get_object_or_404(ExamSession, id=session_id)
        
        # Log the action before deleting
        AuditLog.objects.create(
            actor=request.user,
            action='DELETE',
            target_model='ExamSession',
            details=f"Reset attempt for user {session.user.email} on exam {session.exam.title}"
        )
        
        session.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ExportExamResultsView(views.APIView):
    """
    Admin Only: Downloads an Excel file of all results for a specific exam.
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request, exam_id):
        exam = get_object_or_404(Exam, id=exam_id)
        
        # 1. Setup Excel
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = f'attachment; filename="Results_{exam.title}.xlsx"'
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Exam Results"

        # 2. Header Row
        headers = ['Student Name', 'Email', 'Date Taken', 'Score (%)', 'Status', 'Certificate Code']
        ws.append(headers)
        
        # Style Header
        for cell in ws[1]:
            cell.font = openpyxl.styles.Font(bold=True)

        # 3. Fetch Data
        sessions = ExamSession.objects.filter(exam=exam, end_time__isnull=False).order_by('-score')
        
        for session in sessions:
            cert_code = "N/A"
            if hasattr(session, 'certificate'):
                cert_code = session.certificate.certificate_code
            
            ws.append([
                f"{session.user.first_name} {session.user.last_name}",
                session.user.email,
                session.end_time.strftime('%Y-%m-%d %H:%M'),
                session.score,
                "Passed" if session.passed else "Failed",
                cert_code
            ])

        wb.save(response)
        return response

class DownloadResultView(views.APIView):
    """
    Generates a PDF Result Slip (Transcript) for any completed exam, 
    regardless of pass/fail status.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, session_id):
        # 1. Fetch Session
        if request.user.is_staff:
             session = get_object_or_404(ExamSession, id=session_id)
        else:
             session = get_object_or_404(ExamSession, id=session_id, user=request.user)

        if not session.end_time:
             return Response({"error": "Exam not completed"}, status=400)

        # 2. Setup PDF
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        # 3. Draw Content
        # Header
        p.setFont("Helvetica-Bold", 20)
        p.drawCentredString(width/2, height - 50, "EXAMINATION RESULT SLIP")
        
        p.line(50, height - 60, width - 50, height - 60)

        # Details
        y = height - 100
        p.setFont("Helvetica", 12)
        
        details = [
            f"Candidate Name:  {session.user.first_name} {session.user.last_name}",
            f"Email Address:   {session.user.email}",
            f"Exam Title:      {session.exam.title}",
            f"Date Taken:      {session.end_time.strftime('%Y-%m-%d %H:%M')}",
            f"Status:          {'PASSED' if session.passed else 'FAILED'}"
        ]

        for line in details:
            p.drawString(70, y, line)
            y -= 25

        # Score Box
        y -= 20
        p.rect(70, y - 40, width - 140, 50, stroke=1, fill=0)
        p.setFont("Helvetica-Bold", 16)
        p.drawString(90, y - 25, f"Total Score: {session.score}%")

        # Footer
        p.setFont("Helvetica", 10)
        p.drawCentredString(width/2, 50, "This result slip is computer generated and requires no signature.")

        p.showPage()
        p.save()
        
        buffer.seek(0)
        filename = f"Result_{session.user.first_name}_{session.exam.title}.pdf"
        return FileResponse(buffer, as_attachment=True, filename=filename)