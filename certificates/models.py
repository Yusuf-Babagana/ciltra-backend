from django.db import models
import uuid

class Certificate(models.Model):
    # Use string reference to avoid circular imports
    session = models.OneToOneField(
        'assessments.ExamSession', 
        on_delete=models.CASCADE, 
        related_name='certificate'
    )
    
    certificate_code = models.CharField(max_length=50, unique=True, blank=True)
    issued_at = models.DateTimeField(auto_now_add=True)
    
    # --- NEW FIELDS FOR REVOCATION ---
    is_revoked = models.BooleanField(default=False)
    revocation_reason = models.TextField(blank=True, null=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.certificate_code:
            self.certificate_code = f"CERT-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        status = " (REVOKED)" if self.is_revoked else ""
        return f"Certificate: {self.certificate_code} - {self.session.user.email}{status}"
