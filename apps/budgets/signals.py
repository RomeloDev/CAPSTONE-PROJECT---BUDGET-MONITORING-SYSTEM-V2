from django.db import transaction
from django.db.models import F
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver

from .models import (
    ApprovedBudget,
    BudgetAllocation,
    DepartmentPRE,
    PurchaseRequest,
    ActivityDesign,
    DepartmentPRESupportingDocument,
    PurchaseRequestSupportingDocument,
    ActivityDesignSupportingDocument,
    BudgetRealignmentSupportingDocument,
    PurchaseRequestApprovedDocument,
    ActivityDesignApprovedDocument,
    SupportingDocument,
)


def _apply_budget_delta(approved_budget_id, delta):
    """
    Apply a signed delta to ApprovedBudget.remaining_budget.
    Positive delta adds back funds; negative delta deducts funds.
    """
    if not approved_budget_id or delta == 0:
        return

    ApprovedBudget.all_objects.filter(pk=approved_budget_id).update(
        remaining_budget=F('remaining_budget') + delta
    )


@receiver(pre_save, sender=BudgetAllocation)
def cache_old_allocation_values(sender, instance, **kwargs):
    """
    Cache old values before save so we can compute the exact delta in post_save.
    """
    if not instance.pk:
        instance._old_allocated_amount = None
        instance._old_approved_budget_id = None
        return

    old_instance = BudgetAllocation.all_objects.filter(pk=instance.pk).only(
        'allocated_amount', 'approved_budget_id'
    ).first()

    if old_instance:
        instance._old_allocated_amount = old_instance.allocated_amount
        instance._old_approved_budget_id = old_instance.approved_budget_id
    else:
        instance._old_allocated_amount = None
        instance._old_approved_budget_id = None


@receiver(post_save, sender=BudgetAllocation)
def sync_parent_budget_on_allocation_save(sender, instance, created, **kwargs):
    """
    Keep parent ApprovedBudget.remaining_budget in sync with allocation changes.

    Rules:
    - Create: deduct full allocated amount from parent.
    - Update same parent budget: deduct/add the difference only.
    - Update with parent budget change: return old amount to old parent, then
      deduct new amount from new parent.
    """
    with transaction.atomic():
        if created:
            _apply_budget_delta(instance.approved_budget_id, -instance.allocated_amount)
            return

        old_amount = getattr(instance, '_old_allocated_amount', None)
        old_budget_id = getattr(instance, '_old_approved_budget_id', None)

        if old_amount is None or old_budget_id is None:
            old_instance = BudgetAllocation.all_objects.filter(pk=instance.pk).only(
                'allocated_amount', 'approved_budget_id'
            ).first()
            if not old_instance:
                return
            old_amount = old_instance.allocated_amount
            old_budget_id = old_instance.approved_budget_id

        new_amount = instance.allocated_amount
        new_budget_id = instance.approved_budget_id

        if old_budget_id == new_budget_id:
            delta = new_amount - old_amount
            _apply_budget_delta(new_budget_id, -delta)
        else:
            _apply_budget_delta(old_budget_id, old_amount)
            _apply_budget_delta(new_budget_id, -new_amount)


@receiver(post_delete, sender=BudgetAllocation)
def restore_parent_budget_on_allocation_delete(sender, instance, **kwargs):
    """Return allocated funds back to the parent budget when allocation is deleted."""
    with transaction.atomic():
        _apply_budget_delta(instance.approved_budget_id, instance.allocated_amount)


# ---------------------------------------------------------------------------
# Converted PDF Orphan Cleanup
# Delete the converted PDF file from disk whenever the parent record is deleted.
# ---------------------------------------------------------------------------

@receiver(post_delete, sender=DepartmentPRE)
def cleanup_pre_excel_pdf(sender, instance, **kwargs):
    """Remove converted PRE Excel PDF when the PRE record is deleted."""
    if instance.uploaded_excel_pdf:
        instance.uploaded_excel_pdf.delete(save=False)


@receiver(post_delete, sender=PurchaseRequest)
def cleanup_pr_document_pdf(sender, instance, **kwargs):
    """Remove converted PR document PDF when the PR record is deleted."""
    if instance.uploaded_document_pdf:
        instance.uploaded_document_pdf.delete(save=False)


@receiver(post_delete, sender=ActivityDesign)
def cleanup_ad_document_pdf(sender, instance, **kwargs):
    """Remove converted AD document PDF when the AD record is deleted."""
    if instance.uploaded_document_pdf:
        instance.uploaded_document_pdf.delete(save=False)


@receiver(post_delete, sender=DepartmentPRESupportingDocument)
def cleanup_pre_supporting_doc_pdf(sender, instance, **kwargs):
    """Remove converted PDF when a PRE supporting document is deleted."""
    if instance.converted_pdf:
        instance.converted_pdf.delete(save=False)


@receiver(post_delete, sender=PurchaseRequestSupportingDocument)
def cleanup_pr_supporting_doc_pdf(sender, instance, **kwargs):
    """Remove converted PDF when a PR supporting document is deleted."""
    if instance.converted_pdf:
        instance.converted_pdf.delete(save=False)


@receiver(post_delete, sender=ActivityDesignSupportingDocument)
def cleanup_ad_supporting_doc_pdf(sender, instance, **kwargs):
    """Remove converted PDF when an AD supporting document is deleted."""
    if instance.converted_pdf:
        instance.converted_pdf.delete(save=False)


@receiver(post_delete, sender=BudgetRealignmentSupportingDocument)
def cleanup_br_supporting_doc_pdf(sender, instance, **kwargs):
    """Remove converted PDF when a budget realignment supporting document is deleted."""
    if instance.converted_pdf:
        instance.converted_pdf.delete(save=False)


@receiver(post_delete, sender=PurchaseRequestApprovedDocument)
def cleanup_pr_approved_doc_pdf(sender, instance, **kwargs):
    """Remove converted PDF when a PR approved document is deleted."""
    if instance.converted_pdf:
        instance.converted_pdf.delete(save=False)


@receiver(post_delete, sender=ActivityDesignApprovedDocument)
def cleanup_ad_approved_doc_pdf(sender, instance, **kwargs):
    """Remove converted PDF when an AD approved document is deleted."""
    if instance.converted_pdf:
        instance.converted_pdf.delete(save=False)


@receiver(post_delete, sender=SupportingDocument)
def cleanup_ab_supporting_doc_pdf(sender, instance, **kwargs):
    """Remove converted PDF when an approved-budget supporting document is deleted."""
    if instance.converted_pdf:
        instance.converted_pdf.delete(save=False)