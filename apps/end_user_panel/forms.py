from django import forms
from django.core.exceptions import ValidationError
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