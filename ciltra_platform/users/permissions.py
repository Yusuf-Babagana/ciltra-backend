from rest_framework import permissions

class IsAdmin(permissions.BasePermission):
    """
    Allows access only to Superusers or Admin role.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.role == 'admin' or request.user.is_staff
        )

class IsTeacher(permissions.BasePermission):
    """
    Allows access to Teachers (Examiners) and Admins.
    Teachers can manage exams and questions.
    """
    def has_permission(self, request, view):
        # Allow if user is Teacher OR Admin
        return request.user.is_authenticated and (
            request.user.role == 'teacher' or 
            request.user.role == 'admin' or 
            request.user.is_staff
        )

class IsStudent(permissions.BasePermission):
    """
    Allows access to Students (Candidates).
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'student'