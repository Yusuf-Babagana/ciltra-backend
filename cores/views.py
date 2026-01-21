from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from .models import PlatformSetting, AuditLog
from .serializers import PlatformSettingSerializer, AuditLogSerializer

class PlatformSettingView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        settings = PlatformSetting.load()
        serializer = PlatformSettingSerializer(settings)
        return Response(serializer.data)

    def put(self, request):
        settings = PlatformSetting.load()
        serializer = PlatformSettingSerializer(settings, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            # Auto-Log this action
            AuditLog.objects.create(
                actor=request.user,
                action='SETTINGS',
                target_model='PlatformSetting',
                details='Updated platform configuration variables'
            )
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class AuditLogListView(generics.ListAPIView):
    # Select related avoids N+1 queries when fetching users
    queryset = AuditLog.objects.select_related('actor').all().order_by('-timestamp')
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdminUser]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        action = self.request.query_params.get('action')
        if action:
            queryset = queryset.filter(action=action)
        return queryset