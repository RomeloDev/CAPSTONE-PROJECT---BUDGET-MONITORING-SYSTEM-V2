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
        # 1. Capture Previous Snapshot (Force fresh DB read for safety if needed, 
        # but using the instance provided is standard if it's locked properly)
        # For strict accuracy, we use the value currently on the object.
        previous_balance = allocation.allocated_amount
        
        # 2. Calculate New Balance
        # Ensure amount is Decimal to avoid float errors
        amount_decimal = Decimal(str(amount))
        new_balance = previous_balance + amount_decimal
        
        # 3. Create Atomic Audit Record
        BudgetTransaction.objects.create(
            allocation=allocation,
            transaction_type=transaction_type,
            amount=amount_decimal,
            previous_balance=previous_balance,
            new_balance=new_balance,
            remarks=remarks,
            created_by=user
        )
        
        # 4. Update Parent (Optional Side Effect)
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
