from .models import AuditTrail
def log_activity(user, action, detail, model_name=None, record_id=None, request=None):
    ip = request.META.get('REMOTE_ADDR') if request else None
    AuditTrail.objects.create(
        user=user,
        action=action,
        detail=detail,
        model_name=model_name or '',
        record_id=record_id,
        ip_address=ip
    )