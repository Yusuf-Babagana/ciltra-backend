# certificates/models.py
import uuid
from django.db import models
from assessments.models import ExamSession

class Certificate(models.Model):
    session = models.OneToOneField(ExamSession, on_delete=models.CASCADE, related_name='certificate')
    
    # Unique slug for the public URL (e.g., /verify/7f3a-92b1...)
    verification_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    issued_at = models.DateTimeField(auto_now_add=True)
    
    # CPT Metadata for the public record
    language_pair = models.CharField(max_length=20)
    specialization = models.CharField(max_length=50, default="General")

    file_url = models.URLField(null=True, blank=True) # Link to generated PDF
    
    def __str__(self):
        return f"Certificate for {self.session.user.email} - {self.verification_token}"

    @property
    def verification_url(self):
        return f"https://ciltra.org/verify/{self.verification_token}"