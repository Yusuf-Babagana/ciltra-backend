import io
import qrcode
import os
import requests 
from django.http import FileResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404
# --- FIX 1: Added 'response' to imports ---
from rest_framework import views, permissions, generics, response
from rest_framework_simplejwt.authentication import JWTAuthentication
# --- FIX 2: Added 'AllowAny' to imports ---
from rest_framework.permissions import IsAuthenticated, AllowAny

# ReportLab for PDF generation
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader 
from django.utils import timezone

# Models
from .models import Certificate
from .serializers import CertificateSerializer
from assessments.models import ExamSession
from cores.models import PlatformSetting 

# ==========================================
#               STUDENT VIEWS
# ==========================================

class StudentCertificateListView(generics.ListAPIView):
    """
    Returns a list of all certificates earned by the logged-in student.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CertificateSerializer

    def get_queryset(self):
        return Certificate.objects.filter(session__user=self.request.user).order_by('-issued_at')


class DownloadCertificateView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        # 1. Validation Logic
        if request.user.is_staff:
             session = get_object_or_404(ExamSession, id=session_id)
        else:
             session = get_object_or_404(ExamSession, id=session_id, user=request.user)

        pass_mark = getattr(session.exam, 'passing_score', 50)
        current_score = session.score if session.score is not None else 0
        
        if current_score < pass_mark:
            return HttpResponseForbidden("Exam not passed.")

        cert, _ = Certificate.objects.get_or_create(session=session)
        
        # 2. LOAD ADMIN SETTINGS
        platform_settings = PlatformSetting.load()

        # 3. Generate PDF
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=landscape(A4))
        width, height = landscape(A4)

        # --- A. INSERT LOGO FROM URL (Requested) ---
        logo_url = "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQWsq2XyXP8SEteZmX4r9NT2_DP--oOzMhhFg&s"
        logo_drawn = False

        try:
            res = requests.get(logo_url, timeout=5)
            if res.status_code == 200:
                logo_data = io.BytesIO(res.content)
                # Draw Logo Top-Center
                p.drawImage(ImageReader(logo_data), width/2 - 1*inch, height - 2.5*inch, width=2*inch, preserveAspectRatio=True, mask='auto')
                logo_drawn = True
        except Exception as e:
            print(f"Could not load logo from URL: {e}")

        # Fallback: If URL fails, try local settings
        if not logo_drawn and platform_settings.certificate_logo:
            try:
                logo_path = platform_settings.certificate_logo.path
                if os.path.exists(logo_path):
                    p.drawImage(logo_path, width/2 - 1*inch, height - 2.5*inch, width=2*inch, preserveAspectRatio=True, mask='auto')
            except Exception as e:
                print(f"Could not load local logo: {e}")

        # --- B. TEXT CONTENT ---
        p.setFont("Helvetica-Bold", 30)
        p.drawCentredString(width/2, height - 3.2*inch, "CERTIFICATE OF COMPLETION")
        
        p.setFont("Helvetica", 18)
        p.drawCentredString(width/2, height - 4.2*inch, "This is to certify that")
        
        # Student Name
        student_name = f"{session.user.first_name} {session.user.last_name}".upper()
        p.setFont("Times-BoldItalic", 32)
        p.drawCentredString(width/2, height - 5.2*inch, student_name)

        p.setFont("Helvetica", 16)
        p.drawCentredString(width/2, height - 6.0*inch, "Has successfully completed the examination for")
        
        p.setFont("Helvetica-Bold", 22)
        p.drawCentredString(width/2, height - 6.6*inch, session.exam.title)

        # --- C. INSERT ADMIN SIGNATURE ---
        if platform_settings.certificate_signature:
            try:
                sig_path = platform_settings.certificate_signature.path
                if os.path.exists(sig_path):
                    # Draw Signature Bottom-Right
                    p.drawImage(sig_path, width - 4*inch, 1.8*inch, width=2*inch, height=1*inch, mask='auto')
            except Exception as e:
                print(f"Could not load signature: {e}")

        # Signature Line & Name
        p.setLineWidth(1)
        p.line(width - 4*inch, 1.6*inch, width - 1*inch, 1.6*inch) 
        
        signer_name = platform_settings.certificate_signer_name or "Director"
        signer_title = platform_settings.certificate_signer_title or "Admin"

        p.setFont("Helvetica", 14)
        p.drawCentredString(width - 2.5*inch, 1.3*inch, signer_name)
        
        p.setFont("Helvetica-Oblique", 10)
        p.drawCentredString(width - 2.5*inch, 1.0*inch, signer_title)

        # --- D. DYNAMIC QR CODE ---
        host = request.get_host()
        protocol = "https" if request.is_secure() else "http"
        verification_url = f"{protocol}://{host}/verify/{cert.certificate_code}"
        
        qr_img = qrcode.make(verification_url)
        qr_buffer = io.BytesIO()
        qr_img.save(qr_buffer, format="PNG")
        qr_buffer.seek(0)
        
        # Draw QR Code (Bottom Left)
        p.drawImage(ImageReader(qr_buffer), 1*inch, 1*inch, width=1.5*inch, height=1.5*inch)
        
        p.setFont("Helvetica", 9)
        p.drawString(1*inch, 0.8*inch, f"ID: {cert.certificate_code}")

        p.showPage()
        p.save()
        buffer.seek(0)
        return FileResponse(buffer, as_attachment=True, filename=f"Certificate_{cert.certificate_code}.pdf")


# --- UPDATE 1: Inventory View (Include User Details) ---
class CertificateInventoryView(generics.ListAPIView):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = CertificateSerializer
    # Order by revocation status (revoked first) then date
    queryset = Certificate.objects.all().order_by('-is_revoked', '-issued_at')

# --- UPDATE 2: Verification View (Check Revocation) ---
class VerifyCertificateView(views.APIView):
    permission_classes = [AllowAny] 

    def get(self, request, code):
        try:
            cert = Certificate.objects.get(certificate_code__iexact=code)
        except Certificate.DoesNotExist:
            return response.Response({"is_valid": False, "status": "not_found"}, status=404)
        
        # Check Revocation
        if cert.is_revoked:
             return response.Response({
                "is_valid": False,
                "status": "revoked",
                "revocation_reason": cert.revocation_reason,
                "certificate_code": cert.certificate_code,
                "student_name": f"{cert.session.user.first_name} {cert.session.user.last_name}",
                "exam_title": cert.session.exam.title,
                "issued_at": cert.issued_at,
            })

        return response.Response({
            "is_valid": True,
            "status": "valid",
            "certificate_code": cert.certificate_code,
            "student_name": f"{cert.session.user.first_name} {cert.session.user.last_name}",
            "exam_title": cert.session.exam.title,
            "issued_at": cert.issued_at,
            "score": cert.session.score
        })

# --- NEW VIEW: Revoke Certificate ---
class RevokeCertificateView(views.APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk):
        cert = get_object_or_404(Certificate, id=pk)
        reason = request.data.get('reason', 'Administrative decision')
        
        if cert.is_revoked:
             return response.Response({"message": "Already revoked"}, status=400)

        cert.is_revoked = True
        cert.revocation_reason = reason
        cert.revoked_at = timezone.now()
        cert.save()
        
        return response.Response({"status": f"Certificate {cert.certificate_code} has been revoked."})