from django.db import models
from django.conf import settings

class AuditTrail(models.Model):
    ACTION_CHOICES = (
        ('CREATE', 'Created'),
        ('UPDATE', 'Updated'),
        ('DELETE', 'Deleted'),
        ('LOGIN', 'Logged In'),
        ('LOGOUT', 'Logged Out'),
        ('APPROVE', 'Approved'),
        ('REJECT', 'Rejected'),
        ('ARCHIVE', 'Archived'),
        ('UNARCHIVE', 'Unarchived'),
        ('PASSWORD_RESET_REQUEST', 'Password Reset Requested'),
        ('PASSWORD_RESET_COMPLETE', 'Password Reset Completed'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100)  # Which model was affected
    record_id = models.CharField(max_length=100, null=True)  # ID of the affected record
    detail = models.TextField()  # Description of what happened
    ip_address = models.GenericIPAddressField(null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Audit Trail"
        verbose_name_plural = "Audit Trails"

    def __str__(self):
        return f"{self.user} - {self.action} - {self.timestamp}"
