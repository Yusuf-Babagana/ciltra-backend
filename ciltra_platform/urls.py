from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter

# --- Import Core Views ---
from users.views import (
    RegisterView, 
    CustomLoginView, 
    UserProfileView,
    CandidateListView, 
    UserViewSet,
    ExaminerManagementView
)
from exams.views import ExamViewSet, QuestionViewSet, CategoryViewSet, list_backups, perform_restore,download_backup, delete_backup, create_backup_view
from assessments.views import (
    PendingGradingListView, 
    SubmitGradeView, 
    StartExamView, 
    SubmitExamView, 
    StudentExamAttemptsView, 
    ExamSessionDetailView,
    AdminStatsView,
    AdminAnalyticsView,
    GradedHistoryListView,
    
     # <--- NEW IMPORT
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
router.register(r'users', UserViewSet, basename='users')

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
    path('api/admin/analytics/', AdminAnalyticsView.as_view(), name='admin-analytics'),

    path('api/admin/certificates/', CertificateInventoryView.as_view(), name='admin-certificates'),
    # --- Candidate Management ---
    path('api/admin/candidates/', CandidateListView.as_view(), name='admin-candidates'),
    
    # --- Examiner Dashboard & Grading ---
    path('api/admin/grading/pending/', PendingGradingListView.as_view(), name='grading-pending'),
    path('api/admin/grading/submit/<int:session_id>/', SubmitGradeView.as_view(), name='grading-submit'),
    
    # --- NEW: Exam History Results ---
    path('api/admin/grading/history/', GradedHistoryListView.as_view(), name='grading-history'), 

    # --- Student Dashboard & Exam Taking ---
    path('api/exams/attempts/', StudentExamAttemptsView.as_view(), name='student-attempts'),
    path('api/exams/<int:exam_id>/start/', StartExamView.as_view(), name='start_exam'),
    path('api/exams/session/<int:session_id>/submit/', SubmitExamView.as_view(), name='submit_exam'),
    path('api/exams/session/<int:pk>/', ExamSessionDetailView.as_view(), name='session_detail'),
    
    # --- Certificates ---
    path('api/certificates/', StudentCertificateListView.as_view(), name='student-certificates'),
    path('api/certificates/download/<int:session_id>/', DownloadCertificateView.as_view(), name='download-certificate'),
    
    # --- Assessments App ---
    path('api/assessments/', include('assessments.urls')),

    # --- Examiner Management ---
    path('api/admin/examiners/', ExaminerManagementView.as_view(), name='admin-examiners'),

    # --- Router Routes ---
    path('api/', include(router.urls)),
    path('api/core/', include('cores.urls')),
    path('api/certificates/', include('certificates.urls')),

   # 1. MOVE BACKUP ROUTES HERE (Above the router)
    path('api/admin/backups/list/', list_backups, name='admin-backups-list'),
    path('api/admin/backups/restore/', perform_restore, name='admin-backups-restore'),
    path('api/admin/backups/download/<str:filename>/', download_backup, name='admin-backups-download'),
    path('api/admin/backups/delete/<str:filename>/', delete_backup, name='admin-backups-delete'),
    path('api/admin/backups/create/', create_backup_view, name='admin-backups-create'),
    

]