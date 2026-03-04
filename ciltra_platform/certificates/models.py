# certificates/models.py
import uuid
from django.db import models
from assessments.models import ExamSession

class Certificate(models.Model):
    # Unique ID for public verification (3.3.1)
    certificate_id = models.CharField(max_length=50, unique=True, default=uuid.uuid4)
    session = models.OneToOneField(ExamSession, on_delete=models.CASCADE, related_name='certificate')
    
    issued_at = models.DateTimeField(auto_now_add=True)
    file_url = models.URLField(null=True, blank=True) # Link to generated PDF
    
    def __str__(self):
        return f"Cert {self.certificate_id} for {self.session.user}"

    @property
    def verification_url(self):
        return f"https://ciltra.org/verify/{self.certificate_id}"