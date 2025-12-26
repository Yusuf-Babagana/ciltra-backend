# ciltra_platform/exams/serializers.py
from rest_framework import serializers
from .models import Exam, Question, Option, ExamCategory

# --- Helper Serializers ---

class OptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Option
        fields = ['id', 'text', 'is_correct']

class ExamCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamCategory
        fields = '__all__'

# --- Question Serializers ---

class QuestionSerializer(serializers.ModelSerializer):
    # Map frontend 'question_text' to backend 'text'
    question_text = serializers.CharField(source='text')
    # Map frontend options array (strings) to backend Options models
    options = serializers.ListField(child=serializers.CharField(), required=False, write_only=True)
    options_data = OptionSerializer(source='options', many=True, read_only=True)
    
    # Read-only field to show exam title
    exam_title = serializers.CharField(source='exam.title', read_only=True)

    class Meta:
        model = Question
        fields = [
            'id', 'exam', 'exam_title', 'question_text', 'question_type', 
            'category', 'difficulty', 'points', 'correct_answer', 
            'options', 'options_data'
        ]

    def create(self, validated_data):
        options_text = validated_data.pop('options', [])
        
        # Normalize question type from frontend (essay/translation -> theory)
        q_type = validated_data.get('question_type')
        if q_type in ['essay', 'translation']:
            validated_data['question_type'] = 'theory'
            
        question = Question.objects.create(**validated_data)

        # Handle MCQ Options
        if options_text:
            correct_ans = validated_data.get('correct_answer', '')
            for opt_text in options_text:
                # Simple logic: if option text matches correct_answer, mark it true
                is_correct = (opt_text.strip().lower() == correct_ans.strip().lower())
                Option.objects.create(question=question, text=opt_text, is_correct=is_correct)
        
        return question

# --- Exam Serializers ---

class ExamSerializer(serializers.ModelSerializer):
    # Map frontend 'passing_score' to backend 'pass_mark_percentage'
    passing_score = serializers.IntegerField(source='pass_mark_percentage')
    
    # Handle category as string (name) instead of ID
    category = serializers.CharField()
    
    # Read-only counts
    total_questions = serializers.IntegerField(source='questions.count', read_only=True)

    class Meta:
        model = Exam
        fields = [
            'id', 'title', 'description', 'category', 
            'duration_minutes', 'passing_score', 'price', 
            'currency', 'is_active', 'total_questions'
        ]

    def create(self, validated_data):
        # Extract category name and find/create the object
        cat_name = validated_data.pop('category')
        category_obj, _ = ExamCategory.objects.get_or_create(name=cat_name)
        
        # Create exam with the linked category object
        exam = Exam.objects.create(category=category_obj, **validated_data)
        return exam

    def update(self, instance, validated_data):
        if 'category' in validated_data:
            cat_name = validated_data.pop('category')
            category_obj, _ = ExamCategory.objects.get_or_create(name=cat_name)
            instance.category = category_obj
        
        return super().update(instance, validated_data)

class ExamListSerializer(serializers.ModelSerializer):
    category = serializers.CharField(source='category.name')
    class Meta:
        model = Exam
        fields = ['id', 'title', 'category', 'price', 'duration_minutes']

class ExamDetailSerializer(ExamSerializer):
    """Detailed view for candidates"""
    questions = QuestionSerializer(many=True, read_only=True)
    class Meta(ExamSerializer.Meta):
        fields = ExamSerializer.Meta.fields + ['questions']

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