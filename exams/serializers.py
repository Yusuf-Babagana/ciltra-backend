from rest_framework import serializers
from django.apps import apps
from .models import Exam, Question, Option, ExamCategory
from payments.models import Payment
from assessments.models import ExamSession
from django.utils import timezone

# --- 1. Helper Serializers ---

class OptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Option
        fields = ['id', 'text', 'is_correct']

class ExamCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamCategory
        fields = '__all__'

# --- 2. Question Serializers ---

class QuestionSerializer(serializers.ModelSerializer):
    question_text = serializers.CharField(source='text')
    options = serializers.ListField(child=serializers.CharField(), required=False, write_only=True)
    options_data = OptionSerializer(source='options', many=True, read_only=True)
    exam_title = serializers.CharField(source='exam.title', read_only=True)

    class Meta:
        model = Question
        fields = [
            'id', 'exam', 'exam_title', 'question_text', 'question_type', 
            'points', 'section', 'negative_points',
            'options', 'options_data'
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['options'] = data.pop('options_data') 
        return data

    def create(self, validated_data):
        options_text = validated_data.pop('options', [])
        q_type = validated_data.get('question_type')
        if q_type in ['essay', 'translation']:
            validated_data['question_type'] = 'theory'
            
        question = Question.objects.create(**validated_data)

        if options_text:
            correct_ans = validated_data.get('correct_answer', '')
            for opt_text in options_text:
                is_correct = (opt_text.strip() == correct_ans.strip()) if correct_ans else False
                Option.objects.create(question=question, text=opt_text, is_correct=is_correct)
        
        return question

# --- 3. Exam Serializers ---

class ExamSerializer(serializers.ModelSerializer):
    passing_score = serializers.IntegerField(source='pass_mark_percentage')
    category = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    total_questions = serializers.IntegerField(source='questions.count', read_only=True)

    class Meta:
        model = Exam
        fields = [
            'id', 'title', 'description', 'category', 
            'duration_minutes', 'passing_score', 'grading_type',
            'price', 'is_active', 'total_questions',
            'randomize_questions'
        ]

    def create(self, validated_data):
        cat_name = validated_data.pop('category', None)
        category_obj = None
        if cat_name:
            category_obj, _ = ExamCategory.objects.get_or_create(name=cat_name)
        
        exam = Exam.objects.create(category=category_obj, **validated_data)
        return exam

    def update(self, instance, validated_data):
        if 'category' in validated_data:
            cat_name = validated_data.pop('category')
            if cat_name:
                category_obj, _ = ExamCategory.objects.get_or_create(name=cat_name)
                instance.category = category_obj
            else:
                instance.category = None
        return super().update(instance, validated_data)

class ExamListSerializer(serializers.ModelSerializer):
    # --- FIX: Use SerializerMethodField to handle NoneType safely ---
    category = serializers.SerializerMethodField()
    has_paid = serializers.SerializerMethodField()

    class Meta:
        model = Exam
        fields = ['id', 'title', 'category', 'price', 'duration_minutes', 'grading_type', 'has_paid']

    def get_category(self, obj):
        # If category is None, return "General"
        return obj.category.name if obj.category else "General"

    def get_has_paid(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        if obj.price == 0:
            return True
        return Payment.objects.filter(user=request.user, exam=obj, status='success').exists()

class ExamDetailSerializer(ExamSerializer):
    questions = QuestionSerializer(many=True, read_only=True)
    class Meta(ExamSerializer.Meta):
        fields = ExamSerializer.Meta.fields + ['questions']

# --- 4. Session & Submission Serializers ---

class ExamSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamSession
        fields = '__all__'

class ExamSessionStartSerializer(serializers.ModelSerializer):
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

class AnswerSubmitSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    answer = serializers.CharField(allow_blank=True)

class ExamSubmitSerializer(serializers.Serializer):
    answers = AnswerSubmitSerializer(many=True)