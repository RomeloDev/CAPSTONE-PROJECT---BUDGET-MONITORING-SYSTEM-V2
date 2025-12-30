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