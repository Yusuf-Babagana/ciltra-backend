from rest_framework import serializers
from .models import ExamSession, StudentAnswer
from exams.serializers import ExamListSerializer, ExamDetailSerializer # <--- Ensure ExamDetailSerializer is imported

class StudentAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentAnswer
        fields = ['id', 'question', 'selected_option', 'text_answer', 'awarded_marks', 'grader_comment']
        read_only_fields = ['awarded_marks', 'grader_comment']

class ExamSessionSerializer(serializers.ModelSerializer):
    """Lightweight serializer for lists / dashboard history."""
    exam = ExamListSerializer(read_only=True)
    answers = StudentAnswerSerializer(many=True, read_only=True)
    status = serializers.SerializerMethodField()
    
    class Meta:
        model = ExamSession
        fields = ['id', 'exam', 'start_time', 'end_time', 'score', 'passed', 'is_graded', 'answers', 'status']
        read_only_fields = ['score', 'passed', 'start_time', 'end_time', 'is_graded']

    def get_status(self, obj):
        if obj.end_time:
            return "completed"
        return "in_progress"

class ActiveExamSessionSerializer(ExamSessionSerializer):
    """Heavy serializer for taking the exam. Includes QUESTIONS."""
    exam = ExamDetailSerializer(read_only=True)