from django import forms
from django.core.exceptions import ValidationError
from apps.budgets.models import ActivityDesign

class PurchaseRequestUploadForm(forms.Form):
    """
    Form for uploading Purchase Request document.
    """
    pr_document = forms.FileField(
        label="PR Document",
        help_text="Upload PDF, DOC, or DOCX up to 10MB.",
        required=True
    )
    def clean_pr_document(self):
        pr_file = self.cleaned_data.get('pr_document')
        if pr_file:
            if pr_file.size > 10 * 1024 * 1024:
                raise ValidationError("File size must be less than 10MB.")
            valid_extensions = ['.pdf', '.doc', '.docx']
            if not any(pr_file.name.lower().endswith(ext) for ext in valid_extensions):
                raise ValidationError("Invalid file type. Allowed: PDF, DOC, DOCX.")
        return pr_file
class PurchaseRequestSupportingDocForm(forms.Form):
    """Form for supporting documents."""
    supporting_documents = forms.FileField(
        label="Supporting Documents",
        required=True,
        widget=forms.FileInput() # Do not pass attrs={'multiple': True} here to avoid ValueError
    )
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Apply strict 'multiple' attribute here to bypass Widget constructor check
        self.fields['supporting_documents'].widget.attrs.update({'multiple': True})
class PurchaseRequestDetailsForm(forms.Form):
    """
    Form for final submission details.
    """
    budget_allocation = forms.IntegerField(required=True, widget=forms.HiddenInput())
    # source_of_fund value format: "pre_id|line_item_id|quarter"
    source_of_fund = forms.CharField(required=True)
    total_amount = forms.DecimalField(max_digits=15, decimal_places=2, required=True)
    purpose = forms.CharField(widget=forms.Textarea, required=True)
    
    
class ActivityDesignUploadForm(forms.Form):
    """
    Form for uploading Activity Design document (Step 1).
    """
    ad_document = forms.FileField(
        label="AD Document",
        help_text="Upload PDF, DOC, or DOCX up to 10MB.",
        required=True
    )
    def clean_ad_document(self):
        f = self.cleaned_data.get('ad_document')
        if f:
            if f.size > 10 * 1024 * 1024:
                raise ValidationError("File size must be less than 10MB.")
            valid_extensions = ['.pdf', '.doc', '.docx']
            if not any(f.name.lower().endswith(ext) for ext in valid_extensions):
                raise ValidationError("Invalid file type. Allowed: PDF, DOC, DOCX.")
        return f
class ActivityDesignSupportingDocForm(forms.Form):
    """Form for supporting documents (Step 2)."""
    supporting_documents = forms.FileField(
        label="Supporting Documents",
        required=True,
        widget=forms.FileInput() 
    )
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['supporting_documents'].widget.attrs.update({'multiple': True})
class ActivityDesignDetailsForm(forms.ModelForm):
    """
    Form for final submission details (Step 3).
    We use ModelForm here for easier Model mapping, but we validate manually in view too.
    """
    class Meta:
        model = ActivityDesign
        fields = ['purpose', 'total_amount']
        widgets = {
            'purpose': forms.Textarea(attrs={'rows': 3, 'class': 'form-input'}),
        }
    
    total_amount = forms.DecimalField(required=False, widget=forms.HiddenInput())
    # Extra field for the raw JSON data
    line_items_data = forms.CharField(widget=forms.HiddenInput(), required=True)
    budget_allocation = forms.IntegerField(widget=forms.HiddenInput(), required=True)


class PREBudgetRealignmentForm(forms.Form):
    """
    Form for Creating PRE Budget Realignment Request.
    """
    source_category = forms.ChoiceField(
        label="Source Line Item (Transfer FROM)",
        choices=[],
        required=True
    )
    target_category = forms.ChoiceField(
        label="Target Line Item (Transfer TO)",
        choices=[],
        required=True
    )
    reason = forms.CharField(
        label="Reason for Realignment",
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Optional reason...'}),
        required=False
    )
    
    # Quarterly Amounts
    q1_amount = forms.DecimalField(min_value=0, decimal_places=2, initial=0, required=False)
    q2_amount = forms.DecimalField(min_value=0, decimal_places=2, initial=0, required=False)
    q3_amount = forms.DecimalField(min_value=0, decimal_places=2, initial=0, required=False)
    q4_amount = forms.DecimalField(min_value=0, decimal_places=2, initial=0, required=False)
    
    documents = forms.FileField(
        label="Supporting Documents",
        required=True,
        widget=forms.FileInput()
    )

    def __init__(self, *args, **kwargs):
        source_choices = kwargs.pop('source_choices', [])
        target_choices = kwargs.pop('target_choices', [])
        super().__init__(*args, **kwargs)
        self.fields['source_category'].choices = [('', '-- Select source line item --')] + source_choices
        self.fields['target_category'].choices = [('', '-- Select target line item --')] + target_choices
        # Enable multiple file selection
        self.fields['documents'].widget.attrs.update({'multiple': True})

    def clean(self):
        cleaned_data = super().clean()
        source = cleaned_data.get('source_category')
        target = cleaned_data.get('target_category')
        
        if source and target and source == target:
            self.add_error('target_category', "Source and target categories cannot be the same.")
            
        # Validate total amount > 0
        q1 = cleaned_data.get('q1_amount') or 0
        q2 = cleaned_data.get('q2_amount') or 0
        q3 = cleaned_data.get('q3_amount') or 0
        q4 = cleaned_data.get('q4_amount') or 0
        
        if (q1 + q2 + q3 + q4) <= 0:
            raise ValidationError("Total amount must be greater than zero. Please enter at least one quarterly amount.")
            
        return cleaned_data