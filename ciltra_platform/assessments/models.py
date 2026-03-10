# assessments/models.py
from django.db import models
from django.conf import settings
from exams.models import Exam, Question, Option


class ExamSession(models.Model):
    """Tracks a candidate's specific attempt at an exam."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)  # When they submitted
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    passed = models.BooleanField(null=True)

    # Status for grading workflow
    is_graded = models.BooleanField(default=False)  # False if theory questions need manual review

    # --- DOUBLE-BLIND GRADING ---
    grader_one = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='graded_sessions_one',
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    grader_two = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='graded_sessions_two',
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    moderator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='moderated_sessions',
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    requires_moderation = models.BooleanField(default=False)

    # Section-specific scores for CPT reporting
    score_section_a = models.FloatField(default=0.0, help_text="Section A: Core Knowledge score")
    score_section_b = models.FloatField(default=0.0, help_text="Section B: Practical Competence score")
    score_section_c = models.FloatField(default=0.0, help_text="Section C: Tools / Oral score")

    def __str__(self):
        return f"{self.user} - {self.exam.title}"


class StudentAnswer(models.Model):
    session = models.ForeignKey(ExamSession, related_name='answers', on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)

    # For MCQ
    selected_option = models.ForeignKey(Option, null=True, blank=True, on_delete=models.SET_NULL)

    # For Theory
    text_answer = models.TextField(null=True, blank=True)

    # Grading
    awarded_marks = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    grader_comment = models.TextField(blank=True)  # Feedback from examiner

    # --- CPT RUBRIC DIMENSIONS ---
    accuracy_score = models.FloatField(default=0.0, help_text="Max 40 — fidelity to source meaning")
    style_score = models.FloatField(default=0.0, help_text="Max 25 — register, fluency, readability")
    terminology_score = models.FloatField(default=0.0, help_text="Max 15 — correct use of domain terms")
    presentation_score = models.FloatField(default=0.0, help_text="Max 10 — formatting, layout, conventions")
    ethics_score = models.FloatField(default=0.0, help_text="Max 10 — confidentiality, professional conduct")

    class Meta:
        unique_together = ('session', 'question')


class IntegrityLog(models.Model):
    EVENT_TYPES = [
        ('TAB_SWITCH', 'Tab Switch / Navigation'),
        ('PASTE_ATTEMPT', 'Paste Detected'),
        ('RE_ENTRY', 'Session Re-entry'),
    ]
    
    session = models.ForeignKey(ExamSession, related_name='integrity_logs', on_delete=models.CASCADE)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    details = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.event_type} - {self.session.user.email}"


class Result(models.Model):
    """
    Stores finalized CPT scores (15/65/20) for a candidate.
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='result')
    ca_score = models.FloatField(default=0.0, help_text="15% weight")
    exam_score = models.FloatField(default=0.0, help_text="65% weight")
    practical_score = models.FloatField(default=0.0, help_text="20% weight")
    is_finalized = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Result: {self.user.email} - {self.total_score}%"

    @property
    def total_score(self):
        return round(self.ca_score + self.exam_score + self.practical_score, 2)