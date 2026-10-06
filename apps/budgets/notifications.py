"""
Notification service for the Budget Monitoring System.

Provides two public helpers:
    notify_admins_new_request(request_obj, request_type)
    notify_user_status_change(request_obj, request_type, new_status)

Both are fire-and-forget: failures are logged to stderr but never bubble up
to the caller, so email issues never break core request flows.
"""
import traceback
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

# ─── Internal helpers ────────────────────────────────────────────────────────

def _get_admin_emails():
    """Return a list of email addresses for all active admin (is_staff=True) users."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return list(
        User.objects.filter(is_staff=True, is_active=True)
        .exclude(email='')
        .values_list('email', flat=True)
    )


def _send(subject, template_name, context, recipient_list):
    """
    Render an HTML email from *template_name*, then send it.
    Falls back silently on any error.
    """
    try:
        if not recipient_list:
            return
        from_email = settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER
        html_body  = render_to_string(template_name, context)
        text_body  = strip_tags(html_body)

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=from_email,
            to=recipient_list,
        )
        msg.attach_alternative(html_body, 'text/html')
        msg.send(fail_silently=False)
    except Exception:
        # Never let email failures crash a view
        traceback.print_exc()


# ─── Label helpers ────────────────────────────────────────────────────────────

_TYPE_LABELS = {
    'pre':         'Project Resource Estimate (PRE)',
    'pr':          'Purchase Request (PR)',
    'ad':          'Activity Design (AD)',
    'realignment': 'Budget Realignment',
}

_STATUS_SUBJECT = {
    'Partially Approved': 'Partially Approved',
    'Approved':           'Approved ✓',
    'Rejected':           'Rejected ✗',
}


# ─── Public API ───────────────────────────────────────────────────────────────

def notify_admins_new_request(request_obj, request_type: str):
    """
    Email all admin staff when an end-user submits a new request.

    Parameters
    ----------
    request_obj : model instance
        The newly created PRE / PR / AD / Realignment object.
    request_type : str
        One of: 'pre', 'pr', 'ad', 'realignment'
    """
    admin_emails = _get_admin_emails()
    if not admin_emails:
        return

    label = _TYPE_LABELS.get(request_type, request_type.upper())
    subject = f'[Budget System] New {label} Submitted'

    # Build a display number / ID for the email
    display_id = _get_display_id(request_obj, request_type)

    context = {
        'label':         label,
        'display_id':    display_id,
        'submitted_by':  _get_submitted_by(request_obj),
        'department':    getattr(request_obj, 'department', 'N/A'),
        'total_amount':  _get_amount(request_obj),
        'system_name':   getattr(settings, 'SYSTEM_NAME', 'Budget Monitoring System'),
    }
    _send(subject, 'emails/admin_new_request.html', context, admin_emails)


def notify_user_status_change(request_obj, request_type: str, new_status: str):
    """
    Email the submitting end-user when an admin changes the status of their request.

    Parameters
    ----------
    request_obj : model instance
        The PRE / PR / AD / Realignment object whose status changed.
    request_type : str
        One of: 'pre', 'pr', 'ad', 'realignment'
    new_status : str
        The new status string, e.g. 'Approved', 'Rejected', 'Partially Approved'.
    """
    user = _get_submitted_by_user(request_obj)
    if not user or not getattr(user, 'email', None):
        return

    label      = _TYPE_LABELS.get(request_type, request_type.upper())
    status_str = _STATUS_SUBJECT.get(new_status, new_status)
    subject    = f'[Budget System] Your {label} has been {status_str}'
    display_id = _get_display_id(request_obj, request_type)

    context = {
        'label':            label,
        'display_id':       display_id,
        'new_status':       new_status,
        'rejection_reason': getattr(request_obj, 'rejection_reason', '') or '',
        'first_name':       user.get_full_name() or user.username,
        'system_name':      getattr(settings, 'SYSTEM_NAME', 'Budget Monitoring System'),
    }
    _send(subject, 'emails/user_status_update.html', context, [user.email])


# ─── Field accessors (handle model differences) ───────────────────────────────

def _get_display_id(obj, rtype):
    if rtype == 'pr':
        return getattr(obj, 'pr_number', str(obj.id))
    if rtype == 'ad':
        return getattr(obj, 'ad_number', str(obj.id))
    if rtype == 'pre':
        # DepartmentPRE uses UUID as pk
        pk = str(obj.id)
        return f"PRE-{pk[:8].upper()}"
    # Realignment
    return f"REALIGN-{obj.id}"


def _get_submitted_by(obj):
    user = _get_submitted_by_user(obj)
    if user:
        return user.get_full_name() or user.username
    return 'Unknown'


def _get_submitted_by_user(obj):
    return (
        getattr(obj, 'submitted_by', None)
        or getattr(obj, 'requested_by', None)
    )


def _get_amount(obj):
    return getattr(obj, 'total_amount', None) or getattr(obj, 'amount', None)
