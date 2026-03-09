from django.db import models
from django.conf import settings
from cores.models import LanguagePair


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

    # --- CPT ARCHITECTURE EXTENSIONS ---
    # Blueprint flag: True = this is a master template (e.g. "CPT General EN-FR")
    is_blueprint = models.BooleanField(default=False, help_text="Is this a template (e.g., CPT General)?")
    # Self-FK: instance exams point back to their blueprint
    blueprint = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='instances'
    )

    # Language Pair: e.g. EN-FR, FR-EN
    language_pair = models.ForeignKey(LanguagePair, on_delete=models.PROTECT, null=True, blank=True)
    allowed_directions = models.CharField(
        max_length=20,
        default="both",
        choices=[
            ('AtoB', 'A -> B'),
            ('BtoA', 'B -> A'),
            ('both', 'Both Directions'),
        ]
    )

    # CPT Section Weights (should total 100%)
    weight_section_a = models.FloatField(default=15.0, help_text="Section A: Core Knowledge (%)")
    weight_section_b = models.FloatField(default=65.0, help_text="Section B: Practical Competence (%)")
    weight_section_c = models.FloatField(default=20.0, help_text="Section C: Tools / Oral (%)")

    # --- CPT ASSIGNMENT EXTENSIONS ---
    assigned_examiners = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        through='ExaminerAssignment', 
        related_name='assigned_exams'
    )

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
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=EXAMINER_ROLES, default='content')
    
    # Mandatory CPT Conflict of Interest declaration
    has_declared_no_conflict = models.BooleanField(default=False)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'exam')

    def __str__(self):
        return f"{self.user} assigned to {self.exam}"


class Question(models.Model):
    class QuestionType(models.TextChoices):
        MCQ = "mcq", "Multiple Choice"
        THEORY = "theory", "Theory / Translation"  # Updated label

    class Difficulty(models.TextChoices):
        EASY = "easy", "Easy"
        MEDIUM = "medium", "Medium"
        HARD = "hard", "Hard"

    # Nullable Exam: Allows questions to sit in the "Bank" without being assigned
    exam = models.ForeignKey(Exam, related_name='questions', on_delete=models.SET_NULL, null=True, blank=True)

    # Text content
    text = models.TextField()  # Frontend sends 'question_text'
    question_type = models.CharField(max_length=20, choices=QuestionType.choices, default=QuestionType.MCQ)

    # Section mapping (Section A, B, or C)
    section = models.CharField(
        max_length=20, 
        choices=[
            ('Section A', 'Section A: Core Knowledge'),
            ('Section B', 'Section B: Practical Translation'),
            ('Section B1', 'Section B1: General Translation'),
            ('Section B2', 'Section B2: Specialized Translation'),
            ('Section C', 'Section C: Theory / Ethics'),
        ],
        default='Section A'
    )

    # --- CPT TRANSLATION EXTENSIONS ---
    # For Section B: The actual text to be translated
    source_text = models.TextField(blank=True, null=True, help_text="Original text for translation tasks")
    
    # For Grading: The model answer (hidden from candidates)
    reference_translation = models.TextField(blank=True, null=True, help_text="Reference translation for graders")
    
    # Guidelines (e.g., 'Do not translate proper nouns')
    translation_brief = models.TextField(blank=True, null=True)

    # --- B2 TRACK FILTERING ---
    specialization = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        help_text="e.g., Legal, Medical, Academic (For Section B2 filtering)"
    )

    # Metadata for the Bank
    category = models.CharField(max_length=100, blank=True)  # Tagging questions
    difficulty = models.CharField(max_length=20, choices=Difficulty.choices, default=Difficulty.MEDIUM)
    points = models.FloatField(default=1.0) # Changed to float for consistency with other parts

    # Answers
    correct_answer = models.TextField(blank=True, help_text="Correct answer text or reference")

    def __str__(self):
        return f"[{self.section}] {self.exam.title if self.exam else 'Bank'} - {self.text[:30]}"


class Option(models.Model):
    question = models.ForeignKey(Question, related_name='options', on_delete=models.CASCADE)
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.text