from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ExamViewSet, QuestionViewSet, CategoryViewSet

router = DefaultRouter()
router.register(r'exams', ExamViewSet, basename='exams')
router.register(r'questions', QuestionViewSet, basename='questions')
router.register(r'categories', CategoryViewSet, basename='categories')

urlpatterns = [
    path('', include(router.urls)),
]