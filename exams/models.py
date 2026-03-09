from django.db import models
from django.contrib.auth import get_user_model
from cores.models import LanguagePair  # Ensure this import exists

User = get_user_model()

class ExamCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

class Exam(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        ExamCategory, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='exams'
    )
    
    # --- CPT ASSIGNMENT EXTENSIONS ---
    language_pair = models.ForeignKey(LanguagePair, on_delete=models.PROTECT, null=True, blank=True)
    assigned_examiners = models.ManyToManyField(
        User, 
        through='ExaminerAssignment', 
        related_name='assigned_exams'
    )
    
    duration_minutes = models.IntegerField(help_text="Duration in minutes")
    pass_mark_percentage = models.FloatField(default=50.0)
    
    GRADING_TYPES = [
        ('auto', 'Automatic'),
        ('manual', 'Manual / Hybrid'),
    ]
    grading_type = models.CharField(max_length=10, choices=GRADING_TYPES, default='auto')
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

class ExaminerAssignment(models.Model):
    """
    CPT-integrated assignment model to track specific staff roles 
    and conflict-of-interest declarations.
    """
    EXAMINER_ROLES = [
        ('content', 'Content Examiner'),
        ('chief', 'Chief Examiner'),
        ('moderator', 'Moderator'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=EXAMINER_ROLES, default='content')
    
    # Mandatory CPT Conflict of Interest declaration
    has_declared_no_conflict = models.BooleanField(default=False)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'exam')

class Question(models.Model):
    class QuestionType(models.TextChoices):
        MCQ = 'MCQ', 'Multiple Choice'
        THEORY = 'THEORY', 'Theory / Essay'

    class ApprovalStatus(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        REVIEW = 'review', 'Review'
        APPROVED = 'approved', 'Approved'
        LOCKED = 'locked', 'Locked'

    exam = models.ForeignKey(Exam, related_name='questions', on_delete=models.CASCADE)
    section = models.CharField(max_length=100, blank=True, null=True, help_text="e.g., Section A")
    
    # --- CPT CONTENT WORKFLOW ---
    status = models.CharField(
        max_length=20, 
        choices=ApprovalStatus.choices, 
        default=ApprovalStatus.DRAFT
    )
    approved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='approved_questions'
    )
    
    text = models.TextField()
    question_type = models.CharField(
        max_length=10, 
        choices=QuestionType.choices, 
        default=QuestionType.MCQ
    )
    points = models.FloatField(default=1.0)

    def __str__(self):
        return f"[{self.status}] {self.exam.title} - {self.text[:50]}"

class Option(models.Model):
    question = models.ForeignKey(Question, related_name='options', on_delete=models.CASCADE)
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.text