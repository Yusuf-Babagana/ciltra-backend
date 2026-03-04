from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = "student", "Student"  # Changed from CANDIDATE
        TEACHER = "teacher", "Teacher"  # Changed from EXAMINER
        ADMIN = "admin", "Admin"

    # Enforce unique email for authentication
    email = models.EmailField(unique=True) 
    
    # Default role is now STUDENT
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    phone_number = models.CharField(max_length=15, blank=True)
    
    bio = models.TextField(blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)

    # Set email as the main field for authentication
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    def __str__(self):
        return self.email