from django import forms
from apps.budgets.models import BudgetAllocation, ApprovedBudget, DepartmentPRE
from apps.user_accounts.models import User
from django.contrib.auth.hashers import make_password

class BudgetAllocationForm(forms.ModelForm):
    # Field to select Approved Budget (for dropdown selection)
    approved_budget = forms.ModelChoiceField(
        queryset=ApprovedBudget.objects.filter(is_active=True, remaining_budget__gt=0),
        empty_label="--Select Approved Budget--",
        widget=forms.Select(attrs={
            'class': 'w-full border border-gray-300 rounded px-3 py-2 bg-white focus:ring-2 focus:ring-blue-500'
        })
    )
    
    end_user_id = forms.IntegerField(widget=forms.HiddenInput(), required=False)
    
    allocated_amount = forms.DecimalField(
        max_digits=15, 
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'w-full border border-gray-300 rounded px-3 py-2 focus:ring-2 focus:ring-blue-500'})
    )

    class Meta:
        model = BudgetAllocation
        fields = ['approved_budget', 'allocated_amount']
        
    def clean(self):
        cleaned_data = super().clean()
        allocated_amount = cleaned_data.get('allocated_amount')
        approved_budget = cleaned_data.get('approved_budget')
        end_user_id = cleaned_data.get('end_user_id')
        
        if not allocated_amount or allocated_amount <= 0:
            self.add_error('allocated_amount', "Allocation amount must be greater than 0.")
            return
        
        # --- Context Handling (Create vs Edit) ---
        # If instance.pk exists, we are EDITING
        if self.instance.pk:
            current_allocation = self.instance
            total_used = current_allocation.get_total_used()
            
            if allocated_amount < total_used:
                self.add_error('allocated_amount', f"Cannot reduce allocation below amount already used (₱{total_used:,.2f})")
                return
            
            # Check if we are increasing the budget, do we have enough?
            difference = allocated_amount - current_allocation.allocated_amount
            if difference > 0 and difference > approved_budget.remaining_budget:
                self.add_error('allocated_amount', f"Insufficient remaining budget. Available: ₱{approved_budget.remaining_budget:,.2f}")
                
        # --- Create Mode ---
        else:
            if not end_user_id:
                self.add_error(None, "End User is required.")
                return
            
            try:
                self.end_user = User.objects.get(id=end_user_id)
            except User.DoesNotExist:
                self.add_error(None, "Invalid User selected.")
                return
            
            if allocated_amount > approved_budget.remaining_budget:
                self.add_error('allocated_amount', f"Amount exceeds remaining budget (Available: ₱{approved_budget.remaining_budget:,.2f})")
                
                
class CustomUserCreationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': '...'}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': '...'}))
    
    class Meta:
        model = User
        fields = ['username', 'fullname', 'email', 'position', 'mfo', 'department', 'password']
        
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        if password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match")
            
        return cleaned_data
    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user
class CustomUserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['fullname', 'email', 'position', 'mfo', 'department', 'is_active', 'is_approving_officer']
        
class ApprovedDocumentUploadForm(forms.ModelForm):
    class Meta:
        model = DepartmentPRE
        fields = ['approved_documents'] # Check exact field name in your model