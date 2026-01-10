# ciltra-backend/assessments/urls.py
from django.urls import path
from .views import (
    ResultView, 
    StudentExamAttemptsView, 
    ExamSessionDetailView,
    GetSessionView
)

urlpatterns = [
    # Get Single Result
    path('result/<int:session_id>/', ResultView.as_view(), name='exam-result'),
    
    # Get Exam History
    path('history/', StudentExamAttemptsView.as_view(), name='exam-history'),
    
    # Session Details for Exam Room
    path('session/<int:session_id>/', GetSessionView.as_view(), name='get-session'),
]