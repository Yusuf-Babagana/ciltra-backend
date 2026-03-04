# certificates/views.py
from rest_framework import generics, permissions
from .models import Certificate
from .serializers import CertificateSerializer
# certificates/views.py (Add to existing imports)

class StudentCertificateListView(generics.ListAPIView):
    """List all certificates owned by the logged-in student."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CertificateSerializer

    def get_queryset(self):
        return Certificate.objects.filter(session__user=self.request.user).order_by('-issued_at')


class CertificateInventoryView(generics.ListAPIView):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = CertificateSerializer
    queryset = Certificate.objects.all().order_by('-issued_at')


