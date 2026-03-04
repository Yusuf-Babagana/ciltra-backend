# assessments/permissions.py
from rest_framework import permissions


class IsGraderOrAdmin(permissions.BasePermission):
    """
    Grants access to users whose role is 'admin', 'teacher' (examiner),
    or 'grader', as well as Django staff/superusers.

    Note: 'grader' is an upcoming role for dedicated CPT graders.
          'teacher' maps to the existing Examiner role and is included
          so that current teachers can grade without a schema change.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # Django staff / superusers always have access
        if request.user.is_staff:
            return True

        # Allow the existing teacher role (acts as examiner/grader)
        # and the upcoming dedicated grader role
        allowed_roles = {'admin', 'teacher', 'grader', 'examiner'}
        return getattr(request.user, 'role', None) in allowed_roles
