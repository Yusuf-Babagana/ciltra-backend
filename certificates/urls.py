from django.urls import path
from .views import (
    StudentCertificateListView, 
    DownloadCertificateView, 
    CertificateInventoryView,
    VerifyCertificateView,
    RevokeCertificateView
     # <--- Import this
)

urlpatterns = [
    # Student
    path('', StudentCertificateListView.as_view(), name='student-certificates'),
    path('download/<int:session_id>/', DownloadCertificateView.as_view(), name='download-certificate'),
    
    # Admin
    path('inventory/', CertificateInventoryView.as_view(), name='admin-certificates'),
    
    path('revoke/<int:pk>/', RevokeCertificateView.as_view(), name='revoke-certificate'),

    # --- NEW: Public Verification URL ---
    path('verify/<str:code>/', VerifyCertificateView.as_view(), name='verify-certificate'),
]