from django.db import models
from django.core.cache import cache
from django.conf import settings

class PlatformSetting(models.Model):
    # --- General & Branding ---
    site_name = models.CharField(max_length=100, default="CILTRA CertifyPro")
    support_email = models.EmailField(default="support@ciltra.org")
    maintenance_mode = models.BooleanField(default=False)

    # --- Grading Defaults ---
    default_pass_mark = models.IntegerField(default=60, help_text="Default pass mark percentage")
    default_exam_duration = models.IntegerField(default=120, help_text="Default duration in minutes")
    strict_proctoring = models.BooleanField(default=True)

    # --- Security & Access ---
    max_login_attempts = models.IntegerField(default=5)
    enforce_password_complexity = models.BooleanField(default=True)
    password_min_length = models.IntegerField(default=8)
    require_special_char = models.BooleanField(default=True)

    certificate_logo = models.ImageField(upload_to='settings/cert_logo/', null=True, blank=True)
    certificate_signature = models.ImageField(upload_to='settings/cert_signature/', null=True, blank=True)
    certificate_signer_name = models.CharField(max_length=100, default="Director of Studies")
    certificate_signer_title = models.CharField(max_length=100, default="Registrar")
    certificate_background = models.ImageField(upload_to='settings/cert_background/', null=True, blank=True)
    certificate_stamp = models.ImageField(upload_to='settings/cert_stamp/', null=True, blank=True)
    
    # --- Email Templates ---
    exam_invitation_subject = models.CharField(max_length=200, default="You have been invited to a CILTRA Exam")
    exam_invitation_body = models.TextField(default="Dear {name}, you have been scheduled for an exam...")

    def save(self, *args, **kwargs):
        self.pk = 1  # Singleton pattern
        super().save(*args, **kwargs)
        cache.set('platform_settings', self)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def load(cls):
        obj = cache.get('platform_settings')
        if obj is None:
            obj, created = cls.objects.get_or_create(pk=1)
            cache.set('platform_settings', obj)
        return obj

    def __str__(self):
        return "Platform Settings"


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('LOGIN', 'Login'),
        ('GRADE', 'Grade Submitted'),
        ('CERTIFICATE', 'Certificate Issued'),
        ('SETTINGS', 'Settings Changed'),
    ]

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    target_model = models.CharField(max_length=50, help_text="e.g., Exam, User, Certificate")
    target_object_id = models.CharField(max_length=100, blank=True, null=True)
    details = models.TextField(blank=True, help_text="Description of changes")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.actor} - {self.action} - {self.timestamp}"