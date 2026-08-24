from datetime import datetime
from extensions import db
import models

def sanitize_notification_link(link):
    """
    Open Redirect Protection (Requirement 4).
    Validates that notification links are strictly relative internal paths.
    Rejects external URLs (http://, https://, //, javascript:).
    """
    if not link:
        return None
    link_str = str(link).strip()
    if not link_str.startswith('/'):
        return None
    if link_str.startswith('//'):
        return None
    return link_str

def create_notification(college_id, title, message, category='admissions', user_id=None, recipient_email=None, application_number=None, link=None):
    """
    Creates a tenant-isolated notification record.
    """
    safe_link = sanitize_notification_link(link)
    norm_email = recipient_email.strip().lower() if recipient_email else None

    # Duplicate prevention for identical event status / application
    existing = models.Notification.query.filter_by(
        college_id=college_id,
        user_id=user_id,
        recipient_email=norm_email,
        application_number=application_number,
        title=title,
        message=message
    ).first()

    if existing:
        return existing

    notif = models.Notification(
        college_id=college_id,
        user_id=user_id,
        recipient_email=norm_email,
        application_number=application_number,
        title=title,
        message=message,
        category=category,
        link=safe_link,
        is_read=False
    )
    db.session.add(notif)
    db.session.commit()
    return notif

def notify_college_admins(college_id, title, message, category='admissions', link=None):
    """
    Multi-Admin Dispatch Helper (Requirement 2).
    Notifies all authorized admin accounts associated with the specified tenant.
    """
    admins = models.User.query.filter_by(college_id=college_id).all()
    created_notifs = []
    for admin_user in admins:
        notif = create_notification(
            college_id=college_id,
            user_id=admin_user.id,
            title=title,
            message=message,
            category=category,
            link=link
        )
        created_notifs.append(notif)
    return created_notifs

def get_unread_count_for_context(college_id, user_id=None, email=None, app_num=None):
    """
    Tenant & Recipient Scoped Unread Count (Requirement 1).
    """
    query = models.Notification.query.filter_by(college_id=college_id, is_read=False)
    if user_id:
        query = query.filter_by(user_id=user_id)
    elif email and app_num:
        query = query.filter_by(
            recipient_email=email.strip().lower(),
            application_number=app_num
        )
    else:
        return 0
    return query.count()

def get_notifications_for_context(college_id, user_id=None, email=None, app_num=None, limit=10):
    """
    Tenant & Recipient Scoped Notifications List (Requirement 1).
    """
    query = models.Notification.query.filter_by(college_id=college_id)
    if user_id:
        query = query.filter_by(user_id=user_id)
    elif email and app_num:
        query = query.filter_by(
            recipient_email=email.strip().lower(),
            application_number=app_num
        )
    else:
        return []
    return query.order_by(models.Notification.created_at.desc()).limit(limit).all()

def mark_notification_as_read(notif_id, college_id, user_id=None, email=None, app_num=None):
    """
    Tenant & Recipient Scoped Single Notification Mark As Read (Requirement 1 & CSRF protected).
    """
    query = models.Notification.query.filter_by(id=notif_id, college_id=college_id)
    if user_id:
        query = query.filter_by(user_id=user_id)
    elif email and app_num:
        query = query.filter_by(
            recipient_email=email.strip().lower(),
            application_number=app_num
        )
    else:
        return False

    notif = query.first()
    if notif:
        notif.is_read = True
        db.session.commit()
        return True
    return False

def mark_all_notifications_as_read(college_id, user_id=None, email=None, app_num=None):
    """
    Tenant & Recipient Scoped Bulk Notification Mark As Read (Requirement 1 & CSRF protected).
    """
    query = models.Notification.query.filter_by(college_id=college_id, is_read=False)
    if user_id:
        query = query.filter_by(user_id=user_id)
    elif email and app_num:
        query = query.filter_by(
            recipient_email=email.strip().lower(),
            application_number=app_num
        )
    else:
        return 0

    unread_items = query.all()
    count = len(unread_items)
    for notif in unread_items:
        notif.is_read = True
    db.session.commit()
    return count
