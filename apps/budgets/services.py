from django.db import transaction
from django.utils import timezone
from .models import (
    ApprovedBudget, 
    BudgetAllocation, 
    DepartmentPRE, 
    PurchaseRequest, 
    ActivityDesign, 
    PREBudgetRealignment
)

def archive_budget_cascade(budget_id, archive_type='FISCAL_YEAR', user=None):
    """
    Recursively archives a budget and all its related functional documents.
    Uses QuerySet.update() for performance to avoid N+1 queries.
    
    Args:
        budget_id: The ID of the ApprovedBudget to archive
        archive_type: 'FISCAL_YEAR' (automatic) or 'MANUAL'
        user: The user performing the action (optional)
    """
    
    timestamp = timezone.now()
    
    with transaction.atomic():
        # 1. Archive the Parent (Approved Budget)
        # We fetch specific instance to trigger logic if needed, but use update for consistency if multiple
        ApprovedBudget.all_objects.filter(pk=budget_id).update(
            is_archived=True,
            archive_type=archive_type,
            archived_at=timestamp,
            archived_by=user
        )
        
        # 2. Get Allocations (Level 1)
        # We need the IDs or QuerySet to filter children
        allocation_qs = BudgetAllocation.all_objects.filter(approved_budget_id=budget_id)
        
        # 3. Archive Allocations
        allocation_qs.update(
            is_archived=True,
            archive_type=archive_type,
            archived_at=timestamp,
            archived_by=user
        )
        
        # 4. Level 2: PREs and Realignments
        # DepartmentPREs linked to these allocations
        pre_qs = DepartmentPRE.all_objects.filter(budget_allocation__in=allocation_qs)
        pre_qs.update(
            is_archived=True,
            archive_type=archive_type,
            archived_at=timestamp,
            archived_by=user
        )
        
        # Realignments linked to PREs under these allocations
        # NOTE: Realignments link to source_pre. 
        realignment_qs = PREBudgetRealignment.all_objects.filter(source_pre__budget_allocation__in=allocation_qs)
        realignment_qs.update(
            is_archived=True,
            archive_type=archive_type,
            archived_at=timestamp,
            archived_by=user
        )
        
        # 5. Level 3: PRs and ADs
        # Purchase Requests linked to these allocations
        pr_qs = PurchaseRequest.all_objects.filter(budget_allocation__in=allocation_qs)
        pr_qs.update(
            is_archived=True,
            archive_type=archive_type,
            archived_at=timestamp,
            archived_by=user
        )
        
        # Activity Designs linked to these allocations
        ad_qs = ActivityDesign.all_objects.filter(budget_allocation__in=allocation_qs)
        ad_qs.update(
            is_archived=True,
            archive_type=archive_type,
            archived_at=timestamp,
            archived_by=user
        )
        
        return True

def restore_budget_cascade(budget_id):
    """
    Restores a budget and its children, BUT ONLY those that were archived via cascade (FISCAL_YEAR).
    Prevents restoring manually archived items.
    """
    with transaction.atomic():
        # 1. Restore Parent
        ApprovedBudget.all_objects.filter(pk=budget_id).update(is_archived=False, archive_type='')
        
        # 2. Get Allocations
        allocation_qs = BudgetAllocation.all_objects.filter(approved_budget_id=budget_id)
        
        # 3. Restore Allocations (Only FISCAL_YEAR types)
        allocation_qs.filter(archive_type='FISCAL_YEAR').update(is_archived=False, archive_type='')
        
        # 4. Restore Children (Only FISCAL_YEAR types)
        # PREs
        DepartmentPRE.all_objects.filter(
            budget_allocation__in=allocation_qs, 
            archive_type='FISCAL_YEAR'
        ).update(is_archived=False, archive_type='')
        
        # Realignments
        PREBudgetRealignment.all_objects.filter(
            source_pre__budget_allocation__in=allocation_qs,
            archive_type='FISCAL_YEAR'
        ).update(is_archived=False, archive_type='')
        
        # PRs
        PurchaseRequest.all_objects.filter(
            budget_allocation__in=allocation_qs,
            archive_type='FISCAL_YEAR'
        ).update(is_archived=False, archive_type='')
        
        # ADs
        ActivityDesign.all_objects.filter(
            budget_allocation__in=allocation_qs,
            archive_type='FISCAL_YEAR'
        ).update(is_archived=False, archive_type='')
        
        return True

def archive_allocation_cascade(allocation_id, archive_type='MANUAL', user=None):
    """
    Recursively archives a BudgetAllocation and all its related documents.
    Used for Admin Action logic.
    """
    timestamp = timezone.now()
    
    with transaction.atomic():
        # 1. Archive the Allocation
        # Use update matches model structure
        allocation_qs = BudgetAllocation.all_objects.filter(pk=allocation_id)
        allocation_qs.update(
            is_archived=True,
            archive_type=archive_type,
            archived_at=timestamp,
            archived_by=user
        )
        
        # 2. Archive Children (PREs, Realignments, PRs, ADs)
        
        # PREs
        pre_qs = DepartmentPRE.all_objects.filter(budget_allocation__in=allocation_qs)
        pre_qs.update(
            is_archived=True,
            archive_type=archive_type,
            archived_at=timestamp,
            archived_by=user
        )
        
        # Realignments
        realignment_qs = PREBudgetRealignment.all_objects.filter(source_pre__budget_allocation__in=allocation_qs)
        realignment_qs.update(
            is_archived=True,
            archive_type=archive_type,
            archived_at=timestamp,
            archived_by=user
        )
        
        # PRs
        pr_qs = PurchaseRequest.all_objects.filter(budget_allocation__in=allocation_qs)
        pr_qs.update(
            is_archived=True,
            archive_type=archive_type,
            archived_at=timestamp,
            archived_by=user
        )
        
        # ADs
        ad_qs = ActivityDesign.all_objects.filter(budget_allocation__in=allocation_qs)
        ad_qs.update(
            is_archived=True,
            archive_type=archive_type,
            archived_at=timestamp,
            archived_by=user
        )
        return True

def restore_allocation_cascade(allocation_id):
    """
    Restores a BudgetAllocation and its children.
    Restores items regardless of archive_type if calling this directly on the allocation,
    assuming admin intent is to force restore.
    """
    with transaction.atomic():
        # 1. Restore the Allocation
        allocation_qs = BudgetAllocation.all_objects.filter(pk=allocation_id)
        allocation_qs.update(is_archived=False, archive_type='')
        
        # 2. Restore Children (Simpler logic than Fiscal Year: just restore everything linked)
        # PREs
        DepartmentPRE.all_objects.filter(budget_allocation__in=allocation_qs).update(is_archived=False, archive_type='')
        
        # Realignments
        PREBudgetRealignment.all_objects.filter(source_pre__budget_allocation__in=allocation_qs).update(is_archived=False, archive_type='')
        
        # PRs
        PurchaseRequest.all_objects.filter(budget_allocation__in=allocation_qs).update(is_archived=False, archive_type='')
        
        # ADs
        ActivityDesign.all_objects.filter(budget_allocation__in=allocation_qs).update(is_archived=False, archive_type='')
        
        return True
