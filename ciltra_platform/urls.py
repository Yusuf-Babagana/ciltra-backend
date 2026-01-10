# ciltra-backend/ciltra_platform/urls.py
from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Import Core Views
from users.views import RegisterView, CustomLoginView, UserProfileView
from exams.views import ExamViewSet, QuestionViewSet, CategoryViewSet
from assessments.views import (
    PendingGradingListView, 
    SubmitGradeView, 
    StartExamView, 
    SubmitExamView, 
    StudentExamAttemptsView, 
    ExamSessionDetailView,
    AdminStatsView,
    ExaminerStatsView,
    GradedHistoryListView,
    GradingSessionDetailView
)

# Import Certificate Views (Ensure these match your certificates/views.py)
from certificates.views import (
    DownloadCertificateView, 
    StudentCertificateListView, 
    CertificateInventoryView
)

# Router Configuration
router = DefaultRouter()
router.register(r'exams', ExamViewSet, basename='exams')
router.register(r'questions', QuestionViewSet, basename='questions')
router.register(r'categories', CategoryViewSet, basename='categories')

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # --- Authentication ---
    path('api/auth/register/', RegisterView.as_view(), name='register'),
    path('api/auth/login/', CustomLoginView.as_view(), name='login'),
    path('api/profile/', UserProfileView.as_view(), name='user-profile'),
    
    # --- Payments ---
    path('api/payments/', include('payments.urls')), 

    # --- Admin Dashboard Stats ---
    path('api/admin/stats/', AdminStatsView.as_view(), name='admin-stats'),

    # --- Examiner Dashboard & Grading ---
    path('api/examiner/stats/', ExaminerStatsView.as_view(), name='examiner-stats'),
    path('api/examiner/history/', GradedHistoryListView.as_view(), name='examiner-history'),
    path('api/admin/grading/pending/', PendingGradingListView.as_view(), name='grading-pending'),
    path('api/admin/grading/session/<int:pk>/', GradingSessionDetailView.as_view(), name='grading-session-detail'),
    path('api/admin/grading/submit/<int:session_id>/', SubmitGradeView.as_view(), name='grading-submit'),

    # --- Student Dashboard & Exam Taking ---
    path('api/exams/attempts/', StudentExamAttemptsView.as_view(), name='student-attempts'),
    path('api/exams/<int:exam_id>/start/', StartExamView.as_view(), name='start_exam'),
    path('api/exams/session/<int:session_id>/submit/', SubmitExamView.as_view(), name='submit_exam'),
    path('api/exams/session/<int:pk>/', ExamSessionDetailView.as_view(), name='session_detail'),
    
    # --- Certificates (Standardized Paths) ---
    path('api/certificates/', StudentCertificateListView.as_view(), name='student-certificates'),
    path('api/certificates/download/<int:session_id>/', DownloadCertificateView.as_view(), name='download-certificate'),
    path('api/admin/certificates/', CertificateInventoryView.as_view(), name='admin-certificates'),

    # --- Assessments App ---
    path('api/assessments/', include('assessments.urls')),
    
    # --- Router Routes ---
    path('api/', include(router.urls)),
]