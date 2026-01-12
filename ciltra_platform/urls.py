# ciltra_platform/urls.py
from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter

# --- Import Core Views ---
from users.views import (
    RegisterView, 
    CustomLoginView, 
    UserProfileView,
    CandidateListView, 
    UserViewSet
)
from exams.views import ExamViewSet, QuestionViewSet, CategoryViewSet
from assessments.views import (
    PendingGradingListView, 
    SubmitGradeView, 
    StartExamView, 
    SubmitExamView, 
    StudentExamAttemptsView, 
    ExamSessionDetailView,
    AdminStatsView
)
from certificates.views import (
    DownloadCertificateView, 
    StudentCertificateListView, 
    CertificateInventoryView
)

# --- Router Configuration ---
router = DefaultRouter()
router.register(r'exams', ExamViewSet, basename='exams')
router.register(r'questions', QuestionViewSet, basename='questions')
router.register(r'categories', CategoryViewSet, basename='categories')
router.register(r'users', UserViewSet, basename='users')  # <--- THIS WAS MISSING

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

    # --- Candidate Management (Fixes the 404 Error) ---
    path('api/admin/candidates/', CandidateListView.as_view(), name='admin-candidates'),  # <--- THIS WAS MISSING

    # --- Examiner Dashboard & Grading ---
    path('api/admin/grading/pending/', PendingGradingListView.as_view(), name='grading-pending'),
    path('api/admin/grading/submit/<int:session_id>/', SubmitGradeView.as_view(), name='grading-submit'),

    # --- Student Dashboard & Exam Taking ---
    path('api/exams/attempts/', StudentExamAttemptsView.as_view(), name='student-attempts'),
    path('api/exams/<int:exam_id>/start/', StartExamView.as_view(), name='start_exam'),
    path('api/exams/session/<int:session_id>/submit/', SubmitExamView.as_view(), name='submit_exam'),
    path('api/exams/session/<int:pk>/', ExamSessionDetailView.as_view(), name='session_detail'),
    
    # --- Certificates ---
    path('api/certificates/', StudentCertificateListView.as_view(), name='student-certificates'),
    path('api/certificates/download/<int:session_id>/', DownloadCertificateView.as_view(), name='download-certificate'),
    path('api/admin/certificates/', CertificateInventoryView.as_view(), name='admin-certificates'),

    # --- Assessments App ---
    path('api/assessments/', include('assessments.urls')),
    
    # --- Router Routes (Exams, Questions, Users) ---
    path('api/', include(router.urls)),
]