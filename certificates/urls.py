from django.urls import path
from .views import DownloadCertificateView

urlpatterns = [
    # CRITICAL FIX: Ensure this says <int:session_id>, NOT <str:certificate_id>
    path('download/<int:session_id>/', DownloadCertificateView.as_view(), name='download-certificate'),
]