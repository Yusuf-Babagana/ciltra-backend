from django.urls import path
from .views import CertificateInventoryView

urlpatterns = [
    path('admin/certificates/', CertificateInventoryView.as_view(), name='admin-certificates'),
    # Add verification URL here later if needed
]