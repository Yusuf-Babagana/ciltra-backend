# ciltra_platform/exams/models.py
from django.db import models

class ExamCategory(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    def __str__(self):
        return self.name

class Exam(models.Model):
    title = models.CharField(max_length=255)
    # Make category optional or handle string in serializer
    category = models.ForeignKey(ExamCategory, on_delete=models.SET_NULL, null=True, related_name='exams')
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    currency = models.CharField(max_length=3, default="NGN")
    
    duration_minutes = models.PositiveIntegerField()
    pass_mark_percentage = models.PositiveIntegerField(default=50)
    
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

class Question(models.Model):
    class QuestionType(models.TextChoices):
        MCQ = "mcq", "Multiple Choice"
        THEORY = "theory", "Open Ended / Translation" # Maps to 'essay'/'translation'

    class Difficulty(models.TextChoices):
        EASY = "easy", "Easy"
        MEDIUM = "medium", "Medium"
        HARD = "hard", "Hard"

    # Nullable Exam: Allows questions to sit in the "Bank" without being assigned
    exam = models.ForeignKey(Exam, related_name='questions', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Text content
    text = models.TextField() # Frontend sends 'question_text'
    question_type = models.CharField(max_length=20, choices=QuestionType.choices, default=QuestionType.MCQ)
    
    # Metadata for the Bank
    category = models.CharField(max_length=100, blank=True) # Tagging questions
    difficulty = models.CharField(max_length=20, choices=Difficulty.choices, default=Difficulty.MEDIUM)
    points = models.PositiveIntegerField(default=1)

    # Answers
    correct_answer = models.TextField(blank=True, help_text="Correct answer text or reference")

    def __str__(self):
        return f"{self.text[:50]}..."

class Option(models.Model):
    question = models.ForeignKey(Question, related_name='options', on_delete=models.CASCADE)
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)