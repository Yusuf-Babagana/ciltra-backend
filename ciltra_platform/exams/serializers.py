# ciltra_platform/exams/serializers.py
from rest_framework import serializers
from .models import Exam, Question, Option, ExamCategory
from cores.models import LanguagePair

class OptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Option
        fields = ['id', 'text', 'is_correct']

class LanguagePairSerializer(serializers.ModelSerializer):
    class Meta:
        model = LanguagePair
        fields = ['id', 'source_language', 'target_language', 'pair_code']

class QuestionSerializer(serializers.ModelSerializer):
    options = OptionSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ['id', 'text', 'question_type', 'category', 'difficulty', 'points', 'options']

class ExamCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamCategory
        fields = '__all__'

class ExamListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for lists (no questions)."""
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = Exam
        fields = ['id', 'title', 'description', 'category_name', 'duration_minutes', 'price', 'is_active', 'created_at']

class ExamSerializer(serializers.ModelSerializer):
    """Standard serializer for Admin CRUD — includes all CPT architecture fields."""
    # Nested read-only view of the linked language pair
    language_pair_data = LanguagePairSerializer(source='language_pair', read_only=True)

    # CPT blueprint/instance fields
    is_blueprint = serializers.BooleanField(default=False)

    # Section weights
    weight_section_a = serializers.FloatField(default=15.0)
    weight_section_b = serializers.FloatField(default=65.0)
    weight_section_c = serializers.FloatField(default=20.0)

    class Meta:
        model = Exam
        fields = [
            'id', 'title', 'description', 'category',
            'is_blueprint', 'blueprint',
            'language_pair', 'language_pair_data', 'allowed_directions',
            'duration_minutes', 'pass_mark_percentage', 'price', 'currency',
            'weight_section_a', 'weight_section_b', 'weight_section_c',
            'is_active', 'created_at',
        ]

class ExamDetailSerializer(serializers.ModelSerializer):
    """Heavy serializer WITH questions."""
    questions = QuestionSerializer(many=True, read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Exam
        fields = ['id', 'title', 'description', 'category', 'category_name', 'duration_minutes', 'pass_mark_percentage', 'price', 'is_active', 'questions']


        
# --- Session Serializers (from previous step) ---
# Ensure these remain available for the Start/Submit logic
from assessments.models import ExamSession
class ExamSessionStartSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(source='exam.questions', many=True, read_only=True)
    exam_title = serializers.CharField(source='exam.title', read_only=True)
    duration_minutes = serializers.IntegerField(source='exam.duration_minutes', read_only=True)
    total_questions = serializers.IntegerField(source='exam.questions.count', read_only=True)
    time_remaining_seconds = serializers.SerializerMethodField()

    class Meta:
        model = ExamSession
        fields = ['id', 'exam_id', 'exam_title', 'duration_minutes', 'total_questions', 'questions', 'start_time', 'time_remaining_seconds']

    def get_time_remaining_seconds(self, obj):
        from django.utils import timezone
        if obj.end_time: return 0
        elapsed = (timezone.now() - obj.start_time).total_seconds()
        total = obj.exam.duration_minutes * 60
        return max(0, int(total - elapsed))

class AnswerSubmitSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    answer = serializers.CharField(allow_blank=True)

class ExamSubmitSerializer(serializers.Serializer):
    answers = AnswerSubmitSerializer(many=True)