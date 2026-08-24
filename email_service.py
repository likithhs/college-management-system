import logging
from flask import render_template, current_app, has_request_context
from flask_mail import Message
from extensions import mail

logger = logging.getLogger('email_service')

# In-memory outbox for local testing & verification
mail_outbox = []

def clear_outbox():
    """Clear all captured emails from outbox (useful for automated test isolation)."""
    mail_outbox.clear()

class OutboxEmail:
    """Convenience wrapper for inspecting sent emails in outbox."""
    def __init__(self, recipients, subject, body, html, sender, tracking_id=None, email_type=None):
        self.recipients = recipients if isinstance(recipients, list) else [recipients]
        self.subject = subject
        self.body = body
        self.html = html
        self.sender = sender
        self.tracking_id = tracking_id
        self.application_number = tracking_id
        self.type = email_type

    def __getitem__(self, item):
        return getattr(self, item)

    def __repr__(self):
        return f"<OutboxEmail to={self.recipients} subject='{self.subject}' tracking_id='{self.tracking_id}'>"

def _dispatch_email(recipients, subject, plain_text_body, html_body, tracking_id=None, email_type=None):
    """Internal helper to dispatch email via Flask-Mail and capture in mail_outbox."""
    try:
        sender = current_app.config.get('MAIL_DEFAULT_SENDER', 'admissions@spmcollege.ac.in') if current_app else 'admissions@spmcollege.ac.in'
        rec_list = recipients if isinstance(recipients, list) else [recipients]
        
        # 1. Create Flask-Mail Message
        msg = Message(
            subject=subject,
            recipients=rec_list,
            body=plain_text_body,
            html=html_body,
            sender=sender
        )
        
        # 2. Record in local outbox for testing & auditing
        outbox_entry = OutboxEmail(
            recipients=rec_list,
            subject=subject,
            body=plain_text_body,
            html=html_body,
            sender=sender,
            tracking_id=tracking_id,
            email_type=email_type
        )
        mail_outbox.append(outbox_entry)
        
        # 3. Dispatch via Flask-Mail
        # If MAIL_SUPPRESS_SEND is True or testing mode, Flask-Mail automatically suppresses real SMTP send
        if current_app and not current_app.config.get('MAIL_SUPPRESS_SEND', True):
            mail.send(msg)
            logger.info(f"SMTP Email sent successfully: '{subject}' to {rec_list}")
        else:
            logger.info(f"Local Email captured in outbox: '{subject}' to {rec_list}")
            
        return True
    except Exception as e:
        logger.error(f"Email dispatch error for '{subject}' to {recipients}: {e}", exc_info=True)
        return False

def _render_email_template(template_name, **context):
    """Helper to render Jinja2 email template safely inside or outside request context."""
    try:
        if current_app and not has_request_context():
            with current_app.test_request_context():
                return render_template(template_name, **context)
        return render_template(template_name, **context)
    except Exception as e:
        logger.warning(f"HTML Template render warning for {template_name}: {e}")
        return None

def send_applicant_confirmation_email(app_record, college):
    """
    Sends an application confirmation email to the student upon submission.
    """
    if not app_record or not app_record.email:
        logger.warning("Cannot send applicant confirmation: Invalid applicant or email.")
        return False
        
    try:
        tracking_id = getattr(app_record, 'application_number', '')
        course = getattr(app_record, 'course', 'N/A')
        full_name = getattr(app_record, 'full_name', 'Applicant')
        status = getattr(app_record, 'status', 'PENDING')
        
        setting = getattr(college, 'settings', None) if college else None
        college_name = getattr(setting, 'college_name', None) or getattr(college, 'name', 'Seshadripuram College')
        
        subject = f"Application Confirmation - {college_name} (ID: {tracking_id})"
        
        # Render HTML
        html_body = _render_email_template('emails/application_submitted.html', app_record=app_record, college=college)

        # Plain Text Fallback
        plain_text_body = (
            f"Dear {full_name},\n\n"
            f"Thank you for submitting your online admission application to {college_name}.\n\n"
            f"Application Details:\n"
            f" - Tracking / Application ID: {tracking_id}\n"
            f" - Course Applied: {course}\n"
            f" - Status: {status}\n\n"
            f"Our Admissions Desk will review your application. Please keep your Tracking ID for future reference.\n\n"
            f"Regards,\n"
            f"Admissions Office\n"
            f"{college_name}"
        )

        return _dispatch_email(
            recipients=[app_record.email],
            subject=subject,
            plain_text_body=plain_text_body,
            html_body=html_body,
            tracking_id=tracking_id,
            email_type='applicant_confirmation'
        )
    except Exception as e:
        logger.error(f"Failed to build applicant confirmation email: {e}", exc_info=True)
        return False

def send_admin_new_application_email(app_record, college):
    """
    Notifies College Admin of a new online application submission.
    """
    if not app_record:
        logger.warning("Cannot send admin notification: Invalid application record.")
        return False
        
    try:
        import os
        setting = getattr(college, 'settings', None) if college else None
        admin_email = os.environ.get('ADMIN_NOTIFICATION_EMAIL') or getattr(setting, 'email_info', None) or 'admin@spmcollege.ac.in'
        tracking_id = getattr(app_record, 'application_number', '')
        course = getattr(app_record, 'course', 'N/A')
        full_name = getattr(app_record, 'full_name', 'Applicant')
        percentage = getattr(app_record, 'percentage', 'N/A')
        college_name = getattr(setting, 'college_name', None) or getattr(college, 'name', 'Seshadripuram College')

        subject = f"New Application Received - {tracking_id} ({full_name})"

        # Render HTML
        html_body = _render_email_template('emails/admin_notification.html', app_record=app_record, college=college)

        # Plain Text Fallback
        plain_text_body = (
            f"New Admission Application Alert\n\n"
            f"Applicant: {full_name}\n"
            f"Tracking ID: {tracking_id}\n"
            f"Course: {course}\n"
            f"Marks/Percentage: {percentage}%\n"
            f"Email: {app_record.email}\n"
            f"Phone: {app_record.phone}\n\n"
            f"Please log into the College Admin Desk to review this submission."
        )

        return _dispatch_email(
            recipients=[admin_email],
            subject=subject,
            plain_text_body=plain_text_body,
            html_body=html_body,
            tracking_id=tracking_id,
            email_type='admin_notification'
        )
    except Exception as e:
        logger.error(f"Failed to build admin notification email: {e}", exc_info=True)
        return False

def send_applicant_status_update_email(app_record, old_status, new_status, college):
    """
    Notifies the student whenever their application status changes.
    Does NOT send duplicate email if old_status == new_status.
    """
    if not app_record or not app_record.email:
        logger.warning("Cannot send status update email: Invalid applicant or email.")
        return False

    # REQUIREMENT 6: Do NOT send duplicate email if status has not changed
    if old_status and old_status.upper() == new_status.upper():
        logger.info(f"Skipping status update email for {app_record.application_number}: status unchanged ({old_status}).")
        return True

    try:
        tracking_id = getattr(app_record, 'application_number', '')
        course = getattr(app_record, 'course', 'N/A')
        full_name = getattr(app_record, 'full_name', 'Applicant')
        setting = getattr(college, 'settings', None) if college else None
        college_name = getattr(setting, 'college_name', None) or getattr(college, 'name', 'Seshadripuram College')
        contact_email = getattr(setting, 'email_info', None) or 'admissions@spmcollege.ac.in'

        status_formatted = new_status.replace('_', ' ').title()
        subject = f"Application Status Update: {status_formatted} - {college_name} (ID: {tracking_id})"

        # Render HTML
        html_body = _render_email_template('emails/status_updated.html', app_record=app_record, old_status=old_status, new_status=new_status, college=college)

        # Plain Text Fallback
        plain_text_body = (
            f"Dear {full_name},\n\n"
            f"Your application status for {course} (ID: {tracking_id}) has been updated.\n\n"
            f"Previous Status: {old_status}\n"
            f"New Status: {new_status}\n\n"
            f"If you have any questions, please contact the Admissions Desk at {contact_email}.\n\n"
            f"Regards,\n"
            f"Admissions Office\n"
            f"{college_name}"
        )

        return _dispatch_email(
            recipients=[app_record.email],
            subject=subject,
            plain_text_body=plain_text_body,
            html_body=html_body,
            tracking_id=tracking_id,
            email_type='status_update'
        )
    except Exception as e:
        logger.error(f"Failed to build applicant status update email: {e}", exc_info=True)
        return False
