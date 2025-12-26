from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

# Import models for aggregation
from assessments.models import ExamSession
from certificates.models import Certificate

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'role', 'is_staff', 'bio', 'avatar']
        read_only_fields = ['is_staff']

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'password', 'role']

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['email'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            role=validated_data.get('role', 'candidate')
        )
        return user

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = UserSerializer(self.user).data
        return data

# --- ADD THIS: Serializer for Candidate List ---
class CandidateListSerializer(serializers.ModelSerializer):
    exams_taken = serializers.SerializerMethodField()
    certificates_earned = serializers.SerializerMethodField()
    last_activity = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'exams_taken', 'certificates_earned', 'last_activity']

    def get_exams_taken(self, obj):
        return ExamSession.objects.filter(user=obj).count()

    def get_certificates_earned(self, obj):
        return Certificate.objects.filter(session__user=obj).count()

    def get_last_activity(self, obj):
        last_session = ExamSession.objects.filter(user=obj).order_by('-start_time').first()
        if last_session:
            return last_session.start_time
        return obj.date_joined