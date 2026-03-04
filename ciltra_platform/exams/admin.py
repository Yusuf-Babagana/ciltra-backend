from django.contrib import admin

# Register your models here.
from .models import Exam, Question, Option, ExamCategory

admin.site.register(Exam)
admin.site.register(Question)
admin.site.register(Option)
admin.site.register(ExamCategory)
