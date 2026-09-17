import io
import os
import logging
from flask import has_request_context, request
import qrcode
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

logger = logging.getLogger('pdf_service')

def get_base_url():
    """Resolves the application base URL for QR code verification links."""
    env_url = os.environ.get('APP_BASE_URL', '').rstrip('/')
    if env_url:
        return env_url
    if has_request_context():
        return request.host_url.rstrip('/')
    return 'http://127.0.0.1:5000'

def generate_qr_code_image(verify_url):
    """Generates an in-memory QR code image buffer."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=4,
        border=2,
    )
    qr.add_data(verify_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f172a", back_color="white")
    
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf

def generate_application_receipt_pdf(app_record, college):
    """
    Generates an official PDF receipt for an AdmissionApplication.
    Uses dynamic institution branding from College & CollegeSetting models.
    """
    buffer = io.BytesIO()
    
    # 1. Extract dynamic branding data
    setting = getattr(college, 'settings', None) if college else None
    college_name = getattr(setting, 'college_name', None) or getattr(college, 'name', 'Seshadripuram College')
    tagline = getattr(setting, 'tagline', None) or 'Affiliated to Bengaluru City University | NAAC Accredited A++'
    accreditation = getattr(setting, 'accreditation', None) or 'NAAC A++ Accredited'
    address = getattr(setting, 'address', None) or 'Seshadripuram Main Campus, Bengaluru - 560020'
    email_info = getattr(setting, 'email_info', None) or 'info@spmcollege.ac.in'
    phone_primary = getattr(setting, 'phone_primary', None) or '+91 6363179389 / 080-22955354'

    # Extract application data
    tracking_id = getattr(app_record, 'application_number', 'N/A')
    full_name = getattr(app_record, 'full_name', 'N/A')
    guardian_name = getattr(app_record, 'guardian_name', 'N/A')
    email = getattr(app_record, 'email', 'N/A')
    phone = getattr(app_record, 'phone', 'N/A')
    course = getattr(app_record, 'course', 'N/A')
    percentage = getattr(app_record, 'percentage', 'N/A')
    status = getattr(app_record, 'status', 'PENDING')
    created_at = getattr(app_record, 'created_at', None)
    date_str = created_at.strftime('%d %B %Y, %I:%M %p') if created_at else 'Current Session'

    # 2. Build Verification QR Code
    base_url = get_base_url()
    verify_url = f"{base_url}/verify-receipt/{tracking_id}"
    qr_buf = generate_qr_code_image(verify_url)

    # 3. Setup ReportLab Document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Custom Paragraph Styles
    title_style = ParagraphStyle(
        'CollegeTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#0f172a'),
        alignment=1 # Center
    )

    tagline_style = ParagraphStyle(
        'CollegeTagline',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#475569'),
        alignment=1
    )

    doc_header_style = ParagraphStyle(
        'DocHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=colors.HexColor('#1e3a8a'),
        alignment=1
    )

    label_style = ParagraphStyle(
        'GridLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=12,
        textColor=colors.HexColor('#475569')
    )

    val_style = ParagraphStyle(
        'GridVal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=12,
        textColor=colors.HexColor('#0f172a')
    )

    status_style = ParagraphStyle(
        'GridStatus',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=12,
        textColor=colors.HexColor('#b45309') if status == 'UNDER_REVIEW' else (
            colors.HexColor('#15803d') if status in ['VERIFIED', 'SEAT_LOCKED'] else colors.HexColor('#1e293b')
        )
    )

    small_text = ParagraphStyle(
        'SmallText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#64748b')
    )

    elements = []

    # Header Section
    elements.append(Paragraph(college_name.upper(), title_style))
    elements.append(Spacer(1, 3))
    elements.append(Paragraph(f"{tagline} | {accreditation}", tagline_style))
    elements.append(Paragraph(f"{address} • Email: {email_info} • Phone: {phone_primary}", tagline_style))
    elements.append(Spacer(1, 10))
    
    # Gold & Navy Separator Line
    elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#f59e0b'), spaceAfter=8))
    
    # Document Title
    elements.append(Paragraph("OFFICIAL ADMISSION APPLICATION RECEIPT", doc_header_style))
    elements.append(Spacer(1, 12))

    # Grid Data Table
    table_data = [
        [
            Paragraph("Tracking / Application ID:", label_style),
            Paragraph(f"<b>{tracking_id}</b>", ParagraphStyle('TID', parent=val_style, fontName='Helvetica-Bold', fontSize=11, textColor=colors.HexColor('#0f172a'))),
            Paragraph("Submission Date:", label_style),
            Paragraph(date_str, val_style)
        ],
        [
            Paragraph("Applicant Full Name:", label_style),
            Paragraph(full_name, val_style),
            Paragraph("Guardian / Father Name:", label_style),
            Paragraph(guardian_name, val_style)
        ],
        [
            Paragraph("Email Address:", label_style),
            Paragraph(email, val_style),
            Paragraph("Phone Contact:", label_style),
            Paragraph(phone, val_style)
        ],
        [
            Paragraph("Course Applied:", label_style),
            Paragraph(f"<b>{course}</b>", val_style),
            Paragraph("Academic Marks / %:", label_style),
            Paragraph(f"{percentage}%", val_style)
        ],
        [
            Paragraph("Current Status:", label_style),
            Paragraph(status, status_style),
            Paragraph("Verification Code:", label_style),
            Paragraph(f"VERIFIED-REG-{tracking_id[-6:]}", val_style)
        ]
    ]

    t = Table(table_data, colWidths=[130, 140, 130, 140])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('PADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))

    elements.append(t)
    elements.append(Spacer(1, 15))

    # QR Code & Verification Box Table
    qr_img = RLImage(qr_buf, width=72, height=72)
    
    verif_text = (
        f"<b>Official Authenticity QR Code</b><br/>"
        f"Scan this QR code using any smartphone or visit:<br/>"
        f"<font color='#2563eb'><u>{verify_url}</u></font><br/><br/>"
        f"<font color='#64748b' size=7.5>This receipt confirms registration in the institutional portal database. "
        f"Admissions are subject to final document verification.</font>"
    )
    
    verif_p = Paragraph(verif_text, ParagraphStyle('Verif', parent=styles['Normal'], fontName='Helvetica', fontSize=8.5, leading=11, textColor=colors.HexColor('#334155')))

    qr_table_data = [
        [qr_img, verif_p]
    ]
    
    qr_t = Table(qr_table_data, colWidths=[85, 455])
    qr_t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#eff6ff')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#bfdbfe')),
        ('PADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))

    elements.append(qr_t)
    elements.append(Spacer(1, 20))

    # Signatory & Watermark Block
    sig_text = (
        "<b>Admissions Desk Officer</b><br/>"
        f"{college_name}<br/>"
        "<i>Digitally Verified & Registered</i>"
    )
    sig_p = Paragraph(sig_text, ParagraphStyle('Sig', parent=styles['Normal'], fontName='Helvetica', fontSize=8.5, leading=11, textColor=colors.HexColor('#0f172a'), alignment=2))
    
    sig_table = Table([["", sig_p]], colWidths=[340, 200])
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
        ('PADDING', (0,0), (-1,-1), 0),
    ]))
    
    elements.append(sig_table)
    elements.append(Spacer(1, 15))

    # Footer Line
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#cbd5e1'), spaceAfter=6))
    elements.append(Paragraph(f"© 2026 {college_name}. All Rights Reserved. Computer-generated official document.", ParagraphStyle('Foot', parent=styles['Normal'], fontName='Helvetica', fontSize=7.5, leading=9, textColor=colors.HexColor('#94a3b8'), alignment=1)))

    # 4. Build PDF
    doc.build(elements)
    
    buffer.seek(0)
    return buffer


def generate_provisional_admission_letter(app_record, college):
    """
    Generates an official Provisional Admission & Seat Locking Letter PDF.
    Only available for applications with status VERIFIED or SEAT_LOCKED.
    Uses dynamic institution branding and QR verification URL.
    """
    buffer = io.BytesIO()
    
    setting = getattr(college, 'settings', None) if college else None
    college_name = getattr(setting, 'college_name', None) or getattr(college, 'name', 'Seshadripuram College')
    tagline = getattr(setting, 'tagline', None) or 'Affiliated to Bengaluru City University | NAAC Accredited A++'
    accreditation = getattr(setting, 'accreditation', None) or 'NAAC A++ Accredited'
    address = getattr(setting, 'address', None) or 'Bengaluru, Karnataka, India'
    contact_email = getattr(setting, 'contact_email', None) or 'admissions@spmcollege.ac.in'
    contact_phone = getattr(setting, 'contact_phone', None) or '+91 80 2295 5354'

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    elements = []

    # 1. College Header Banner
    header_data = [
        [
            Paragraph(f"<b><font size=16 color='#0f172a'>{college_name.upper()}</font></b><br/>"
                      f"<font size=8.5 color='#475569'>{tagline}</font><br/>"
                      f"<font size=8 color='#64748b'>{address} | Email: {contact_email} | Phone: {contact_phone}</font>",
                      ParagraphStyle('HLeft', parent=styles['Normal'], leading=13))
        ]
    ]
    header_table = Table(header_data, colWidths=[540])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#e2e8f0')),
        ('PADDING', (0,0), (-1,-1), 10),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 15))

    # 2. Letter Title Banner
    title_p = Paragraph(
        "OFFICIAL PROVISIONAL ADMISSION LETTER",
        ParagraphStyle('THead', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=14, leading=16, textColor=colors.HexColor('#1e3a8a'), alignment=1)
    )
    elements.append(title_p)
    elements.append(Spacer(1, 12))

    # 3. Applicant & Admission Details Grid
    base_url = get_base_url()
    verify_url = f"{base_url}/verify-receipt/{app_record.application_number}"
    qr_buf = generate_qr_code_image(verify_url)
    qr_img = RLImage(qr_buf, width=70, height=70)

    detail_data = [
        [Paragraph(f"<b>Ref No:</b> PAL/{app_record.application_number}", styles['Normal']), Paragraph(f"<b>Date:</b> {app_record.updated_at.strftime('%d %B %Y') if app_record.updated_at else 'Recent'}", styles['Normal'])],
        [Paragraph(f"<b>Candidate Name:</b> {app_record.full_name}", styles['Normal']), Paragraph(f"<b>Application ID:</b> {app_record.application_number}", styles['Normal'])],
        [Paragraph(f"<b>Guardian Name:</b> {app_record.guardian_name}", styles['Normal']), Paragraph(f"<b>Course Offered:</b> {app_record.course}", styles['Normal'])],
        [Paragraph(f"<b>Percentage / Merit:</b> {app_record.percentage}%", styles['Normal']), Paragraph(f"<b>Status:</b> <font color='#15803d'><b>{app_record.status}</b></font>", styles['Normal'])],
    ]
    detail_table = Table(detail_data, colWidths=[270, 270])
    detail_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#ffffff')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#f1f5f9')),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(detail_table)
    elements.append(Spacer(1, 15))

    # 4. Provisional Admission Terms & Confirmation Body
    body_text = (
        f"Dear <b>{app_record.full_name}</b>,<br/><br/>"
        f"We are pleased to inform you that based on your academic eligibility score of <b>{app_record.percentage}%</b> and verification of credentials, "
        f"you have been provisionally selected for admission to the <b>{app_record.course}</b> program at {college_name} for the Academic Session 2026-27.<br/><br/>"
        "<b>Terms & Next Steps:</b><br/>"
        "1. This provisional admission is subject to final document verification against original mark sheets and certificates.<br/>"
        "2. Please present this Provisional Admission Letter along with original documents to the Admissions Office within 7 working days.<br/>"
        "3. Your seat status is officially registered as <b>SEAT LOCKED</b> in the university portal database.<br/>"
    )
    body_p = Paragraph(body_text, ParagraphStyle('BodyText', parent=styles['Normal'], fontName='Helvetica', fontSize=9.5, leading=14, textColor=colors.HexColor('#1e293b')))
    elements.append(body_p)
    elements.append(Spacer(1, 15))

    # 5. Verification QR Block & Signature
    verif_text = (
        f"<b>Digital Authenticity Verification</b><br/>"
        f"Scan QR code or visit:<br/><font color='#2563eb'><u>{verify_url}</u></font><br/>"
        f"<font color='#64748b' size=7.5>Verification Code: {app_record.application_number}</font>"
    )
    verif_p = Paragraph(verif_text, ParagraphStyle('Verif', parent=styles['Normal'], fontName='Helvetica', fontSize=8.5, leading=11))

    sig_text = (
        "<b>Dean / Admissions Officer</b><br/>"
        f"{college_name}<br/>"
        "<i>Digitally Signed & Certified</i>"
    )
    sig_p = Paragraph(sig_text, ParagraphStyle('Sig', parent=styles['Normal'], fontName='Helvetica', fontSize=8.5, leading=11, alignment=2))

    footer_grid = Table([[qr_img, verif_p, sig_p]], colWidths=[80, 260, 200])
    footer_grid.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(footer_grid)
    elements.append(Spacer(1, 15))

    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#cbd5e1'), spaceAfter=6))
    elements.append(Paragraph(f"© 2026 {college_name}. All Rights Reserved. Computer-generated official document.", ParagraphStyle('Foot', parent=styles['Normal'], fontName='Helvetica', fontSize=7.5, leading=9, textColor=colors.HexColor('#94a3b8'), alignment=1)))

    doc.build(elements)
    buffer.seek(0)
    return buffer


def generate_question_paper_pdf(paper, college=None):
    """
    Generates an authentic, official University Examination Question Paper PDF
    for a given QuestionPaper model record.
    Returns in-memory BytesIO buffer containing the PDF bytes.
    """
    buffer = io.BytesIO()
    setting = getattr(college, 'settings', None) if college else None
    college_name = getattr(setting, 'college_name', None) or getattr(college, 'name', 'Seshadripuram College')
    tagline = getattr(setting, 'tagline', None) or 'Affiliated to Bengaluru City University | NAAC Accredited A++'
    address = getattr(setting, 'address', None) or 'Seshadripuram Main Campus, Bengaluru - 560020'

    course_name = getattr(paper.course, 'name', 'Degree Program') if getattr(paper, 'course', None) else 'Academic Program'
    course_code = getattr(paper.course, 'code', 'Course') if getattr(paper, 'course', None) else 'Course'
    semester = getattr(paper, 'semester', 'Semester')
    year = getattr(paper, 'year', '2026')
    subject = getattr(paper, 'subject', 'University Subject')

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    styles = getSampleStyleSheet()
    elements = []

    # 1. Header Banner
    head_title = Paragraph(f"<font size=16 color='#0f172a'><b>SESHADRIPURAM EDUCATIONAL TRUST</b></font>", ParagraphStyle('H1', parent=styles['Normal'], alignment=1, spaceAfter=2))
    college_title = Paragraph(f"<font size=14 color='#1e3a8a'><b>{college_name.upper()}</b></font>", ParagraphStyle('H2', parent=styles['Normal'], alignment=1, spaceAfter=2))
    affil_title = Paragraph(f"<font size=8.5 color='#475569'>{tagline} • {address}</font>", ParagraphStyle('H3', parent=styles['Normal'], alignment=1, spaceAfter=6))
    
    elements.append(head_title)
    elements.append(college_title)
    elements.append(affil_title)
    elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#1e3a8a'), spaceAfter=8))

    # 2. Exam Meta Box
    exam_subhead = Paragraph(
        f"<b>END SEMESTER DEGREE EXAMINATION — {year}</b><br/>"
        f"<font size=11 color='#0f172a'><b>{course_name.upper()} ({course_code})</b></font>",
        ParagraphStyle('ExamSub', parent=styles['Normal'], alignment=1, spaceAfter=8)
    )
    elements.append(exam_subhead)

    meta_data = [
        [
            Paragraph(f"<b>Subject:</b> {subject}", styles['Normal']),
            Paragraph(f"<b>Semester:</b> {semester}", styles['Normal'])
        ],
        [
            Paragraph(f"<b>Course Code:</b> {course_code}", styles['Normal']),
            Paragraph(f"<b>Examination Year:</b> {year}", styles['Normal'])
        ],
        [
            Paragraph(f"<b>Duration:</b> 3 Hours", styles['Normal']),
            Paragraph(f"<b>Maximum Marks:</b> 100 Marks", styles['Normal'])
        ]
    ]
    meta_table = Table(meta_data, colWidths=[320, 220])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#94a3b8')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('PADDING', (0,0), (-1,-1), 5),
        ('FONTSIZE', (0,0), (-1,-1), 9),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 10))

    # 3. Instructions
    inst_text = (
        "<b>INSTRUCTIONS TO CANDIDATES:</b><br/>"
        "1. Answer all questions from <b>Section A</b>, any <b>FOUR</b> questions from <b>Section B</b>, and any <b>TWO</b> questions from <b>Section C</b>.<br/>"
        "2. Neat diagrams and structural flowcharts should be drawn wherever necessary.<br/>"
        "3. Non-programmable scientific calculators are permitted. Electronic smart devices are strictly prohibited."
    )
    inst_p = Paragraph(inst_text, ParagraphStyle('Inst', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=11, textColor=colors.HexColor('#334155')))
    inst_box = Table([[inst_p]], colWidths=[540])
    inst_box.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#fffbeb')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#fde68a')),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(inst_box)
    elements.append(Spacer(1, 12))

    # 4. Question Paper Sections
    # Section A
    sec_a_header = Paragraph("<b>SECTION — A</b> (Answer any 5 questions. Each question carries 4 marks: 5 × 4 = 20 Marks)", ParagraphStyle('SecA', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, textColor=colors.HexColor('#1e3a8a'), spaceAfter=4))
    elements.append(sec_a_header)
    q_a = [
        f"1. Define the fundamental principles and architectural lifecycle of {subject}.",
        f"2. Explain the key differences between synchronous and asynchronous operations in this domain.",
        f"3. State the core data integrity rules and validation mechanisms applicable to {subject}.",
        f"4. Outline the importance of security authentication and authorization protocols.",
        f"5. What are the standard performance benchmarking criteria used in modern implementations?",
        f"6. Write a short technical note on modularity, scalability, and code maintainability."
    ]
    for q in q_a:
        elements.append(Paragraph(q, ParagraphStyle('Q', parent=styles['Normal'], fontName='Helvetica', fontSize=8.5, leading=12, leftIndent=12, spaceAfter=2)))
    
    elements.append(Spacer(1, 10))

    # Section B
    sec_b_header = Paragraph("<b>SECTION — B</b> (Answer any 4 questions. Each question carries 10 marks: 4 × 10 = 40 Marks)", ParagraphStyle('SecB', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, textColor=colors.HexColor('#1e3a8a'), spaceAfter=4))
    elements.append(sec_b_header)
    q_b = [
        f"7. Elaborate on the end-to-end design patterns and system architecture associated with {subject}. Illustrate with neat block diagrams.",
        f"8. Critically analyze data structure requirements and optimization strategies for high-throughput systems.",
        f"9. Compare and contrast traditional algorithmic approaches versus modern scalable techniques in {subject}.",
        f"10. Discuss database transactions, concurrency control, and fault tolerance mechanisms.",
        f"11. Explain how continuous integration and deployment pipelines ensure quality assurance in production environments."
    ]
    for q in q_b:
        elements.append(Paragraph(q, ParagraphStyle('Q', parent=styles['Normal'], fontName='Helvetica', fontSize=8.5, leading=12, leftIndent=12, spaceAfter=3)))

    elements.append(Spacer(1, 10))

    # Section C
    sec_c_header = Paragraph("<b>SECTION — C</b> (Answer any 2 questions. Each question carries 20 marks: 2 × 20 = 40 Marks)", ParagraphStyle('SecC', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, textColor=colors.HexColor('#1e3a8a'), spaceAfter=4))
    elements.append(sec_c_header)
    q_c = [
        f"12. (a) Design a complete, enterprise-grade architecture for an application utilizing {subject}. Detail all components, layers, interfaces, and communication protocols. (12 Marks)<br/>(b) Formulate an emergency disaster recovery and business continuity plan for this system. (8 Marks)",
        f"13. In-depth Case Study: Analyze a legacy enterprise infrastructure facing high latency and scalability bottlenecks. Formulate a comprehensive migration and modernization roadmap addressing performance, data security, and compliance. (20 Marks)",
        f"14. Discuss emerging innovations, artificial intelligence integrations, and future technological evolutions impacting {subject}. Evaluate real-world industry adoption challenges and solutions. (20 Marks)"
    ]
    for q in q_c:
        elements.append(Paragraph(q, ParagraphStyle('Q', parent=styles['Normal'], fontName='Helvetica', fontSize=8.5, leading=12, leftIndent=12, spaceAfter=5)))

    elements.append(Spacer(1, 14))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#cbd5e1'), spaceAfter=6))

    # 5. Footer Certification
    footer_text = (
        f"<b>Official University Examination Archive</b> • Verified by Controller of Examinations, Seshadripuram College.<br/>"
        f"<font size=7 color='#64748b'>Document Format: Verified PDF • Seshadripuram Educational Trust • Generated from official repository.</font>"
    )
    elements.append(Paragraph(footer_text, ParagraphStyle('Foot', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=10, textColor=colors.HexColor('#64748b'), alignment=1)))

    doc.build(elements)
    buffer.seek(0)
    return buffer

