# ciltra_platform/users/backends.py
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()

class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            # Check if the input matches either the username OR the email
            user = User.objects.get(Q(username=username) | Q(email=username))
        except User.DoesNotExist:
            return None
        except User.MultipleObjectsReturned:
            return User.objects.filter(email=username).order_by('id').first()

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None