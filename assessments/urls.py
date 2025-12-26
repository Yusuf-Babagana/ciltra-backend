from django.urls import path
from .views import PendingGradingListView, SubmitGradeView, StartExamView, SubmitExamView, ExamSessionDetailView

urlpatterns = [
    # --- Grading Module (Admin) ---
    path('admin/grading/pending/', PendingGradingListView.as_view(), name='grading-pending'),
    path('admin/grading/submit/<int:session_id>/', SubmitGradeView.as_view(), name='grading-submit'),

    #Student Exam Flow
    path('api/exams/<int:exam_id>/start/', StartExamView.as_view(), name='start_exam'),
    path('api/exams/session/<int:session_id>/submit/', SubmitExamView.as_view(), name='submit_exam'),


    path('api/exams/session/<int:pk>/', ExamSessionDetailView.as_view(), name='session_detail'),

]