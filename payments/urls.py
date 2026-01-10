from django.urls import path
from .views import VerifyPaystackPaymentView

urlpatterns = [
    # The actual URL will be: /api/payments/verify/
    path('verify/', VerifyPaystackPaymentView.as_view(), name='verify-payment'),
]