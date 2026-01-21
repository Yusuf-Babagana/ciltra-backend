from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

# Import models for aggregation
from assessments.models import ExamSession
from certificates.models import Certificate

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    # Add password field (Write Only ensures it is never sent back in API responses)
    password = serializers.CharField(write_only=True, required=False)
    
    # --- FIX: Explicitly define is_active to ensure it is returned and writable ---
    is_active = serializers.BooleanField(required=False)

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'role', 'is_active', 'date_joined', 'password']
        read_only_fields = ['id', 'date_joined', 'email'] # Prevent email editing here for safety


    def create(self, validated_data):
        """
        Overriding create to hash the password correctly.
        """
        password = validated_data.pop('password', None)
        
        # We use the standard create_user method to handle hashing
        user = User.objects.create_user(
            email=validated_data['email'],
            username=validated_data['email'], # Use email as username
            password=password,
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            role=validated_data.get('role', 'candidate')
        )
        return user

    def update(self, instance, validated_data):
        """
        Allow updating details, but handle password separately if provided.
        """
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
            
        if password:
            instance.set_password(password)
            
        instance.save()
        return instance

        
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