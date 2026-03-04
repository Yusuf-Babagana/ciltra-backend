from rest_framework import serializers
from .models import Certificate

class CertificateSerializer(serializers.ModelSerializer):
    # Fetch details from the related session to show readable names
    candidate_name = serializers.CharField(source='session.user.get_full_name', read_only=True)
    candidate_email = serializers.CharField(source='session.user.email', read_only=True)
    exam_title = serializers.CharField(source='session.exam.title', read_only=True)
    score = serializers.DecimalField(source='session.score', max_digits=5, decimal_places=2, read_only=True)

    class Meta:
        model = Certificate
        fields = [
            'id', 
            'certificate_id', 
            'candidate_name', 
            'candidate_email',
            'exam_title', 
            'score',
            'issued_at', 
            'file_url', 
            'verification_url'
        ]