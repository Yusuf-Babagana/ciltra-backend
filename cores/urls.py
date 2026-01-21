from django.urls import path
from .views import PlatformSettingView, AuditLogListView

urlpatterns = [
    path('settings/', PlatformSettingView.as_view(), name='platform-settings'),
    path('audit-logs/', AuditLogListView.as_view(), name='audit-logs'),
]