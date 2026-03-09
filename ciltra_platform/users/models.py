from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = "student", "Student"  # Changed from CANDIDATE
        TEACHER = "teacher", "Teacher"  # Changed from EXAMINER
        ADMIN = "admin", "Admin"
        GRADER = "grader", "Grader"

    # Enforce unique email for authentication
    email = models.EmailField(unique=True) 
    
    # Default role is now STUDENT
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    phone_number = models.CharField(max_length=15, blank=True)
    
    bio = models.TextField(blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)

    # --- NEW CPT COMPETENCY FIELDS ---
    # Stores pairs like "EN-FR, FR-EN"
    language_pair_competence = models.CharField(max_length=255, blank=True, help_text="Comma-separated language pairs")
    
    # Direction competence: AtoB, BtoA, or both
    direction_competence = models.CharField(max_length=20, default="both", choices=[
        ('AtoB', 'A → B'),
        ('BtoA', 'B → A'),
        ('both', 'Both Directions')
    ])
    
    # Stores tracks like "Legal, Medical"
    specialization_competence = models.CharField(max_length=255, blank=True, help_text="Comma-separated specializations")

    # Set email as the main field for authentication
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    def __str__(self):
        return self.email


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    specialization = models.CharField(max_length=100, blank=True, null=True, help_text="e.g., Legal, Medical, Academic")

    def __str__(self):
        return f"Profile for {self.user.email}"

# Signals to auto-create profile
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()