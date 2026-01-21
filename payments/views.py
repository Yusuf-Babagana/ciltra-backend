import requests
import logging
from django.conf import settings
from django.utils import timezone
from rest_framework import views, permissions, status
from rest_framework.response import Response
from .models import Payment
from exams.models import Exam

logger = logging.getLogger(__name__)

class VerifyPaystackPaymentView(views.APIView):
    """
    Verifies a Reference Code provided manually by the student.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        reference = request.data.get('reference')
        exam_id = request.data.get('exam_id')

        if not reference or not exam_id:
            return Response({"error": "Please enter the Reference Code"}, status=400)

        # 1. Check if this reference was already used
        if Payment.objects.filter(reference=reference).exists():
            return Response({"error": "This payment receipt has already been used."}, status=400)

        # 2. Verify with Paystack
        # Ensure PAYSTACK_SECRET_KEY is in settings.py
        if not hasattr(settings, 'PAYSTACK_SECRET_KEY'):
            logger.error("PAYSTACK_SECRET_KEY missing in settings.")
            return Response({"error": "Server misconfiguration: Missing Paystack Key"}, status=500)

        headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
        url = f"https://api.paystack.co/transaction/verify/{reference}"
        
        try:
            # Timeout is crucial to prevent server hanging
            resp = requests.get(url, headers=headers, timeout=20) 
            resp_data = resp.json()

            if resp_data['status'] and resp_data['data']['status'] == 'success':
                # 3. Validation: Did they pay the correct amount?
                try:
                    exam = Exam.objects.get(id=exam_id)
                except Exam.DoesNotExist:
                    return Response({"error": "Exam not found."}, status=404)

                amount_paid = resp_data['data']['amount'] / 100 # Convert kobo to naira
                
                # Check price (allow floating point tolerance)
                if float(amount_paid) < float(exam.price):
                      return Response({
                          "error": f"Incomplete payment. Exam costs {exam.price} but you paid {amount_paid}"
                      }, status=400)

                # 4. Success! Save the record
                Payment.objects.create(
                    user=request.user,
                    exam=exam,
                    amount=amount_paid,
                    reference=reference,
                    status='success',
                    verified_at=timezone.now()
                )
                return Response({"status": "success", "message": "Payment verified! You can now start."})
            else:
                return Response({"error": "Invalid or failed transaction reference."}, status=400)
                
        except requests.exceptions.Timeout:
            return Response({"error": "Verification timed out. Paystack is slow right now."}, status=504)
            
        except requests.exceptions.ConnectionError:
            return Response({"error": "Network error. Could not connect to Paystack."}, status=503)

        except Exception as e:
            logger.error(f"Payment Verification Error: {str(e)}")
            return Response({"error": "An internal error occurred during verification."}, status=500)