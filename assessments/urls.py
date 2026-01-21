from django.urls import path
from .views import (
    ResultView, 
    StudentExamAttemptsView, 
    ExamSessionDetailView,
    GetSessionView,
    # Admin Views
    AdminStatsView,
    PendingGradingListView,
    SubmitGradeView,
    GradingSessionDetailView,
    ExaminerStatsView,
    GradedHistoryListView,
    AdminAnalyticsView,
    ResetSessionView,
    # --- NEW IMPORT ---
    ExportExamResultsView,
    DownloadResultView
)

urlpatterns = [
    # Student Routes
    path('result/<int:session_id>/', ResultView.as_view(), name='exam-result'),
    path('history/', StudentExamAttemptsView.as_view(), name='exam-history'),
    path('session/<int:session_id>/', GetSessionView.as_view(), name='get-session'),

    # Admin/Grader Routes
    path('admin/stats/', AdminStatsView.as_view(), name='admin-stats'),
    path('admin/analytics/', AdminAnalyticsView.as_view(), name='admin-analytics'),
    
    path('admin/grading/pending/', PendingGradingListView.as_view(), name='grading-pending'),
    path('admin/grading/session/<int:pk>/', GradingSessionDetailView.as_view(), name='grading-detail'),
    path('admin/grading/submit/<int:session_id>/', SubmitGradeView.as_view(), name='grading-submit'),
    path('admin/grading/history/', GradedHistoryListView.as_view(), name='grading-history'),
    
    # --- FIX START: Added these aliases to match the Frontend request ---
    # The frontend is calling /grading/session/15/ (without /admin), so we enable that route here.
    path('grading/session/<int:pk>/', GradingSessionDetailView.as_view(), name='grading-detail-direct'),
    path('grading/submit/<int:session_id>/', SubmitGradeView.as_view(), name='grading-submit-direct'),
    path('grading/pending/', PendingGradingListView.as_view(), name='grading-pending-direct'),
    # --- FIX END ---

    path('grading/history/', GradedHistoryListView.as_view(), name='graded-history'),
    path('examiner/stats/', ExaminerStatsView.as_view(), name='examiner-stats'),

    # Admin Utilities
    path('admin/session/<int:session_id>/reset/', ResetSessionView.as_view(), name='reset-session'),

    path('result/<int:session_id>/download/', DownloadResultView.as_view(), name='download-result'),

    # --- NEW: Export Excel URL ---
    path('admin/export/exam/<int:exam_id>/', ExportExamResultsView.as_view(), name='export-exam-results'),
]