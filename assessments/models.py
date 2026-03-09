# assessments/models.py
from django.db import models
from django.conf import settings
from exams.models import Exam, Question, Option

class ExamSession(models.Model):
    """Tracks a candidate's specific attempt with CPT sectional weighting."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    
    # --- CPT SECTIONAL BREAKDOWN ---
    # Raw percentages per section (0.00 to 100.00)
    score_section_a = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    score_section_b = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    score_section_c = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    
    # Final Weighted Total (A*0.15 + B*0.65 + C*0.20)
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    passed = models.BooleanField(null=True)
    is_graded = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.email} - {self.exam.title} ({self.score}%)"

class StudentAnswer(models.Model):
    session = models.ForeignKey(ExamSession, related_name='answers', on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    
    # MCQ & Theory fields
    selected_option = models.ForeignKey(Option, null=True, blank=True, on_delete=models.SET_NULL)
    text_answer = models.TextField(null=True, blank=True)
    
    # CPT-Integrated Grading
    awarded_marks = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    grader_comment = models.TextField(blank=True)

    class Meta:
        unique_together = ('session', 'question')