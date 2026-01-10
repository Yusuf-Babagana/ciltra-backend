import requests
from django.conf import settings
from django.utils import timezone
from rest_framework import views, permissions, status
from rest_framework.response import Response
from .models import Payment
from exams.models import Exam

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

        # 1. Check if this reference was already used (Prevent reuse!)
        if Payment.objects.filter(reference=reference).exists():
            return Response({"error": "This payment receipt has already been used."}, status=400)

        # 2. Verify with Paystack
        headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
        url = f"https://api.paystack.co/transaction/verify/{reference}"
        
        try:
            # ✅ ADDED TIMEOUT: Stops hanging after 15 seconds
            resp = requests.get(url, headers=headers, timeout=15) 
            resp_data = resp.json()

            if resp_data['status'] and resp_data['data']['status'] == 'success':
                # 3. Validation: Did they pay the correct amount?
                try:
                    exam = Exam.objects.get(id=exam_id)
                except Exam.DoesNotExist:
                    return Response({"error": "Exam not found."}, status=404)

                amount_paid = resp_data['data']['amount'] / 100 # Convert kobo to naira
                
                # Allow a small difference (e.g., fees) or exact match
                # Using float comparison
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
            # Handle slow internet/Paystack down
            return Response({"error": "Verification timed out. Please check your internet and try again."}, status=504)
            
        except requests.exceptions.ConnectionError:
            # Handle no internet
            return Response({"error": "Network error. Could not connect to Paystack."}, status=503)

        except Exception as e:
            # Print the actual error to your terminal for debugging
            print(f"Payment Verification Error: {str(e)}")
            return Response({"error": f"An error occurred: {str(e)}"}, status=500)