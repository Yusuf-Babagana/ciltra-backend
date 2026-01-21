from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class ExamCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

class Exam(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # --- RESTORED CATEGORY FIELD ---
    category = models.ForeignKey(
        ExamCategory, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='exams'
    )

    duration_minutes = models.IntegerField(help_text="Duration in minutes")
    
    # Scoring Rules
    pass_mark_percentage = models.FloatField(default=50.0)
    
    GRADING_TYPES = [
        ('auto', 'Automatic (Instant Result)'),
        ('manual', 'Manual / Hybrid (Wait for Grader)'),
    ]
    grading_type = models.CharField(max_length=10, choices=GRADING_TYPES, default='auto')
    
    randomize_questions = models.BooleanField(default=False)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

class Question(models.Model):
    class QuestionType(models.TextChoices):
        MCQ = 'MCQ', 'Multiple Choice'
        THEORY = 'THEORY', 'Theory / Essay'

    exam = models.ForeignKey(Exam, related_name='questions', on_delete=models.CASCADE)
    section = models.CharField(max_length=100, blank=True, null=True, help_text="e.g., Section A")
    
    text = models.TextField()
    question_type = models.CharField(
        max_length=10, 
        choices=QuestionType.choices, 
        default=QuestionType.MCQ
    )
    points = models.FloatField(default=1.0)
    negative_points = models.FloatField(default=0.0) 

    def __str__(self):
        return f"{self.exam.title} - {self.text[:50]}"

class Option(models.Model):
    question = models.ForeignKey(Question, related_name='options', on_delete=models.CASCADE)
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.text