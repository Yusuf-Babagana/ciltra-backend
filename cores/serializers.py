from rest_framework import serializers
from .models import PlatformSetting, AuditLog

class PlatformSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformSetting
        fields = '__all__'
        read_only_fields = ['id']

class AuditLogSerializer(serializers.ModelSerializer):
    # This field fetches the email from the related User model
    actor_email = serializers.CharField(source='actor.email', read_only=True)
    actor_role = serializers.CharField(source='actor.role', read_only=True)

    class Meta:
        model = AuditLog
        fields = ['id', 'actor', 'actor_email', 'actor_role', 'action', 'target_model', 'target_object_id', 'timestamp', 'details']