from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RegisterView, 
    CustomLoginView, 
    AdminStatsView, 
    StudentListView, # Was CandidateListView
    UserViewSet,
    bulk_register_students
)

# Create a router for ViewSets
router = DefaultRouter()
router.register(r'users', UserViewSet, basename='users')

urlpatterns = [
    # --- Authentication ---
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', CustomLoginView.as_view(), name='login'),

    # --- Admin Dashboard ---
    path('admin/stats/', AdminStatsView.as_view(), name='admin-stats'),
    path('admin/students/', StudentListView.as_view(), name='admin-students'),
    path('admin/bulk-register/', bulk_register_students, name='bulk-register'),

    # --- User Management (CRUD) ---
    path('', include(router.urls)),
]