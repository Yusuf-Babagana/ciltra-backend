# certificates/views.py

import io
from django.http import FileResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from rest_framework import views, permissions, generics
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated

# ReportLab for PDF generation
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.units import inch

# Models & Serializers
from .models import Certificate
from .serializers import CertificateSerializer
from assessments.models import ExamSession

# ==========================================
#              STUDENT VIEWS
# ==========================================

class StudentCertificateListView(generics.ListAPIView):
    """
    Returns a list of all certificates earned by the logged-in student.
    Used for the 'My Certificates' section on the dashboard.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CertificateSerializer

    def get_queryset(self):
        return Certificate.objects.filter(session__user=self.request.user).order_by('-issued_at')


class DownloadCertificateView(views.APIView):
    """
    Generates and downloads the PDF certificate.
    Accessible by:
    - The Student who owns the certificate (if they passed).
    - Admins/Staff (can download ANY certificate).
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        # --- 1. PERMISSION LOGIC ---
        # If Admin/Staff -> Can download ANY session
        # If Student -> Can ONLY download their OWN session
        if request.user.is_staff or request.user.is_superuser:
            session = get_object_or_404(ExamSession, id=session_id)
        else:
            session = get_object_or_404(ExamSession, id=session_id, user=request.user)
        
        # --- 2. VALIDATION ---
        # Check if the student actually passed
        pass_mark = getattr(session.exam, 'passing_score', getattr(session.exam, 'pass_mark_percentage', 50))
        if session.score < pass_mark:
            return HttpResponseForbidden("This candidate has not passed the exam yet.")

        # Ensure Certificate record exists
        cert, created = Certificate.objects.get_or_create(session=session)
        display_id = getattr(cert, 'certificate_code', getattr(cert, 'certificate_id', str(cert.id)))

        # --- 3. PDF GENERATION ---
        buffer = io.BytesIO()
        # Use Landscape A4 for a traditional certificate feel
        p = canvas.Canvas(buffer, pagesize=landscape(A4))
        width, height = landscape(A4)

        # A. PRESTIGE BORDER
        p.setStrokeColorRGB(0.1, 0.1, 0.4) # Dark Navy
        p.setLineWidth(3)
        p.rect(0.4*inch, 0.4*inch, width-0.8*inch, height-0.8*inch) # Outer border
        
        p.setLineWidth(1)
        p.rect(0.5*inch, 0.5*inch, width-1.0*inch, height-1.0*inch) # Inner accent border

        # B. HEADER / LOGO
        p.setFillColorRGB(0.1, 0.1, 0.4)
        p.setFont("Helvetica-Bold", 36)
        p.drawCentredString(width/2.0, height-2*inch, "CILTRA ACADEMY")
        
        p.setStrokeColorRGB(0.7, 0.5, 0.1) # Gold line
        p.setLineWidth(2)
        p.line(width/2.0 - 2*inch, height-2.2*inch, width/2.0 + 2*inch, height-2.2*inch)

        # C. MAIN TEXT
        p.setFillColorRGB(0, 0, 0)
        p.setFont("Helvetica", 18)
        p.drawCentredString(width/2.0, height-3.2*inch, "This acknowledges that")

        # Student Name (Bold & Large)
        student_name = f"{session.user.first_name} {session.user.last_name}".upper()
        p.setFont("Times-BoldItalic", 32)
        p.drawCentredString(width/2.0, height-4*inch, student_name)

        p.setFont("Helvetica", 18)
        p.drawCentredString(width/2.0, height-4.8*inch, "has demonstrated proficiency and successfully passed")
        
        p.setFont("Helvetica-Bold", 22)
        p.drawCentredString(width/2.0, height-5.4*inch, f"The {session.exam.title}")

        # D. FOOTER DETAILS (Score & ID)
        p.setFont("Helvetica", 12)
        p.setFillColorRGB(0.3, 0.3, 0.3) # Gray text
        p.drawString(1*inch, 1.8*inch, f"Date Issued: {cert.issued_at.strftime('%d %B %Y')}")
        p.drawString(1*inch, 1.55*inch, f"Certificate ID: {display_id}")
        p.drawString(1*inch, 1.3*inch, f"Final Grade: {session.score}%")

        # E. SIGNATURE SECTION
        # Registrar Signature line
        p.setStrokeColorRGB(0, 0, 0)
        p.setLineWidth(1)
        p.line(width-3.5*inch, 1.5*inch, width-1*inch, 1.5*inch)
        
        p.setFont("Times-Italic", 14)
        p.drawCentredString(width-2.25*inch, 1.7*inch, "Oluwaseun A. Ciltra") # Example name
        
        p.setFont("Helvetica-Bold", 10)
        p.drawCentredString(width-2.25*inch, 1.3*inch, "DIRECTOR OF STUDIES")

        # F. GOLD SEAL DESIGN (Simulated)
        p.setFillColorRGB(0.8, 0.6, 0.1) # Gold color
        p.circle(width/2.0, 1.5*inch, 0.5*inch, fill=1)
        p.setFillColorRGB(1, 1, 1)
        p.setFont("Helvetica-Bold", 8)
        p.drawCentredString(width/2.0, 1.5*inch, "OFFICIAL")
        p.drawCentredString(width/2.0, 1.4*inch, "SEAL")

        # --- 4. FINALIZE & RETURN ---
        p.showPage()
        p.save()

        buffer.seek(0)
        return FileResponse(buffer, as_attachment=True, filename=f"Certificate_{display_id}.pdf")

        
# ==========================================
#              ADMIN VIEWS
# ==========================================

class CertificateInventoryView(generics.ListAPIView):
    """
    Allows Admins to see all certificates issued across the platform.
    """
    permission_classes = [permissions.IsAdminUser]
    serializer_class = CertificateSerializer
    queryset = Certificate.objects.all().order_by('-issued_at')