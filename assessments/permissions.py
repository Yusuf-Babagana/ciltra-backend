from rest_framework import permissions

class IsGraderOrAdmin(permissions.BasePermission):
    """
    Allows access to Admins, Examiners, and Graders.
    Strictly blocks Candidates.
    """
    def has_permission(self, request, view):
        # 1. User must be logged in
        if not request.user or not request.user.is_authenticated:
            return False

        # 2. Check Role
        # Allow if Superuser/Staff OR Role is in allowed list
        return (
            request.user.is_staff or 
            getattr(request.user, 'role', '') in ['examiner', 'grader', 'admin']
        )