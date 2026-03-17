from django.db import transaction
from django.db.models import F
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver

from .models import ApprovedBudget, BudgetAllocation


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