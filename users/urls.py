from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RegisterView, 
    CustomLoginView, 
    AdminStatsView, 
    CandidateListView, 
    UserViewSet,
    UserProfileView
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
    path('admin/candidates/', CandidateListView.as_view(), name='admin-candidates'),

    path('profile/', UserProfileView.as_view(), name='user-profile'),
    # --- User Management (CRUD) ---
    path('', include(router.urls)),
]