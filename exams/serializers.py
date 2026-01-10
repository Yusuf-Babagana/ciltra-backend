# ciltra_platform/exams/serializers.py
from rest_framework import serializers
from .models import Exam, Question, Option, ExamCategory
from payments.models import Payment
from assessments.models import ExamSession
from django.utils import timezone

# --- 1. Helper Serializers ---

class OptionSerializer(serializers.ModelSerializer):
    """
    Serializer for Options. 
    Note: 'is_correct' is included here for Admin/Grading, 
    but you might want to exclude it for Student views later if security is strict.
    """
    class Meta:
        model = Option
        fields = ['id', 'text', 'is_correct']

class ExamCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamCategory
        fields = '__all__'

# --- 2. Question Serializers ---

class QuestionSerializer(serializers.ModelSerializer):
    # Map frontend 'question_text' to backend 'text'
    question_text = serializers.CharField(source='text')
    
    # 1. WRITE: Map frontend options array (strings) to backend Options models (creation only)
    options = serializers.ListField(child=serializers.CharField(), required=False, write_only=True)
    
    # 2. READ: This field sends the actual Option Objects to the frontend (CRITICAL FIX)
    options_data = OptionSerializer(source='options', many=True, read_only=True)
    
    # Read-only field to show exam title
    exam_title = serializers.CharField(source='exam.title', read_only=True)

    class Meta:
        model = Question
        fields = [
            'id', 'exam', 'exam_title', 'question_text', 'question_type', 
            'category', 'difficulty', 'points', 'correct_answer', 
            'options',      # Write-only (list of strings)
            'options_data'  # Read-only (list of objects with IDs)
        ]

    def to_representation(self, instance):
        """
        Custom fix: The frontend expects 'options' to be the list of objects, 
        but we used 'options' for the write-only list of strings.
        We swap them here so frontend gets what it expects.
        """
        data = super().to_representation(instance)
        data['options'] = data.pop('options_data') # Move options_data -> options
        return data

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

# --- 3. Exam Serializers ---

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
            'currency', 'is_active', 'total_questions',
            'payment_link'
        ]

    def create(self, validated_data):
        cat_name = validated_data.pop('category')
        category_obj, _ = ExamCategory.objects.get_or_create(name=cat_name)
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
    has_paid = serializers.SerializerMethodField()

    class Meta:
        model = Exam
        fields = ['id', 'title', 'category', 'price', 'duration_minutes', 'payment_link', 'has_paid']

    def get_has_paid(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
            
        if obj.price == 0:
            return True
            
        return Payment.objects.filter(
            user=request.user, 
            exam=obj, 
            status='success'
        ).exists()

class ExamDetailSerializer(ExamSerializer):
    """Detailed view for candidates (includes Questions)"""
    questions = QuestionSerializer(many=True, read_only=True)
    
    class Meta(ExamSerializer.Meta):
        fields = ExamSerializer.Meta.fields + ['questions']

# --- 4. Session Serializers ---

class ExamSessionSerializer(serializers.ModelSerializer):
    """Used for displaying session status"""
    class Meta:
        model = ExamSession
        fields = '__all__'

class ExamSessionStartSerializer(serializers.ModelSerializer):
    """Used when Starting an Exam"""
    questions = QuestionSerializer(source='exam.questions', many=True, read_only=True)
    exam_title = serializers.CharField(source='exam.title', read_only=True)
    duration_minutes = serializers.IntegerField(source='exam.duration_minutes', read_only=True)
    total_questions = serializers.IntegerField(source='exam.questions.count', read_only=True)
    time_remaining_seconds = serializers.SerializerMethodField()

    class Meta:
        model = ExamSession
        fields = ['id', 'exam', 'exam_title', 'duration_minutes', 'total_questions', 'questions', 'start_time', 'time_remaining_seconds']

    def get_time_remaining_seconds(self, obj):
        if obj.end_time: return 0
        elapsed = (timezone.now() - obj.start_time).total_seconds()
        total = obj.exam.duration_minutes * 60
        return max(0, int(total - elapsed))

# --- 5. Submission Serializers ---

class AnswerSubmitSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    answer = serializers.CharField(allow_blank=True)

class ExamSubmitSerializer(serializers.Serializer):
    answers = AnswerSubmitSerializer(many=True)