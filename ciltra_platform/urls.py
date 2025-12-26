from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Import Views
from users.views import RegisterView, CustomLoginView
from exams.views import ExamViewSet, QuestionViewSet, CategoryViewSet
from assessments.views import (
    PendingGradingListView, 
    SubmitGradeView, 
    StartExamView, 
    SubmitExamView, 
    StudentExamAttemptsView, 
    ExamSessionDetailView,
    AdminStatsView  # <--- Import this
)
from certificates.views import CertificateInventoryView, StudentCertificateListView

# Router
router = DefaultRouter()
router.register(r'exams', ExamViewSet, basename='exams')
router.register(r'questions', QuestionViewSet, basename='questions')
router.register(r'categories', CategoryViewSet, basename='categories')

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # --- Authentication ---
    path('api/auth/register/', RegisterView.as_view(), name='register'),
    path('api/auth/login/', CustomLoginView.as_view(), name='login'),
    
    # --- Admin Dashboard Stats (NEW) ---
    path('api/admin/stats/', AdminStatsView.as_view(), name='admin-stats'),

    # --- Student Dashboard & Exam Taking ---
    path('api/exams/attempts/', StudentExamAttemptsView.as_view(), name='student-attempts'),
    path('api/exams/<int:exam_id>/start/', StartExamView.as_view(), name='start_exam'),
    path('api/exams/session/<int:session_id>/submit/', SubmitExamView.as_view(), name='submit_exam'),
    path('api/exams/session/<int:pk>/', ExamSessionDetailView.as_view(), name='session_detail'),
    
    # --- Student Certificates ---
    path('api/certificates/', StudentCertificateListView.as_view(), name='student-certificates'),

    # --- Admin Grading Module ---
    path('api/admin/grading/pending/', PendingGradingListView.as_view(), name='grading-pending'),
    path('api/admin/grading/submit/<int:session_id>/', SubmitGradeView.as_view(), name='grading-submit'),
    
    # --- Admin Certificates ---
    path('api/admin/certificates/', CertificateInventoryView.as_view(), name='admin-certificates'),

    # --- Standard API Routes ---
    path('api/', include(router.urls)),
]