from rest_framework import serializers
from .models import Certificate

class CertificateSerializer(serializers.ModelSerializer):
    candidate_name = serializers.SerializerMethodField()
    candidate_email = serializers.ReadOnlyField(source='session.user.email')
    exam_title = serializers.ReadOnlyField(source='session.exam.title')
    score = serializers.ReadOnlyField(source='session.score')
    session_id = serializers.ReadOnlyField(source='session.id')
    certificate_url = serializers.SerializerMethodField()

    # MAP THE FIELD CORRECTLY:
    # If your database model has 'certificate_id', change source='certificate_id'
    # If your database model has NO code and just an ID, use source='id'
    certificate_code = serializers.ReadOnlyField(source='id') 

    class Meta:
        model = Certificate
        fields = [
            'id', 
            'certificate_code', # This now works because of the mapping above
            'session_id',
            'candidate_name', 
            'candidate_email',
            'exam_title', 
            'score',
            'issued_at', 
            'certificate_url'
        ]

    def get_certificate_url(self, obj):
        return f"/api/certificates/download/{obj.session.id}/"

    def get_candidate_name(self, obj):
        user = obj.session.user
        return user.get_full_name() or user.username