from django.db import transaction
from decimal import Decimal
from .models import BudgetTransaction

def log_budget_transaction(allocation, amount, transaction_type, user, remarks='', update_allocation=True):
    """
    Robust utility to handle financial audit logging with Snapshot Logic.
    
    Args:
        allocation: The BudgetAllocation instance.
        amount (Decimal): The amount changing (positive for credit, negative for debit).
        transaction_type (str): e.g., "Realignment", "Expense", "Supplement".
        user: The user making the change.
        remarks (str): Optional text.
        update_allocation (bool): If True, updates the allocation.allocated_amount and saves it.
                                  Set to False if you want to handle the parent update manually
                                  or if this transaction affects a different field (like only remaining_balance).
    """
    with transaction.atomic():
        amount_decimal = Decimal(str(amount))
        new_balance = allocation.allocated_amount 
        previous_balance = allocation.allocated_amount - amount_decimal
        
        BudgetTransaction.objects.create(
            allocation=allocation,
            transaction_type=transaction_type,
            amount=amount_decimal,
            previous_balance=previous_balance,
            new_balance=new_balance,
            remarks=remarks,
            created_by=user
        )
        
        if update_allocation:
            allocation.allocated_amount = new_balance
            
            # Recalculate remaining balance if the allocation changes
            # (Assuming remaining = allocated - used)
            # We call the model's update method if it exists, or do it manually
            if hasattr(allocation, 'update_remaining_balance'):
                allocation.update_remaining_balance()
            else:
                # Fallback manual calculation
                total_used = allocation.get_total_used() if hasattr(allocation, 'get_total_used') else Decimal('0.00')
                allocation.remaining_balance = allocation.allocated_amount - total_used
                allocation.save() # Saved inside the atomic block
