from django.contrib import admin
from .models import ExamSession, StudentAnswer
# Register your models here.

admin.site.register(ExamSession)
admin.site.register(StudentAnswer)