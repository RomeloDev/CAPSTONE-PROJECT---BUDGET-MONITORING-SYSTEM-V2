from django import forms
from .models import ApprovedBudget



class ApprovedBudgetForm(forms.ModelForm):
    # budget_files is handled manually in the template and view
    # to avoid validation issues with multiple file uploads

    class Meta:
        model = ApprovedBudget
        fields = ['title', 'fiscal_year', 'amount', 'description']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full border border-gray-300 rounded px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:outline-none',
                'placeholder': 'e.g., Annual Budget 2026'
            }),
            'fiscal_year': forms.Select(attrs={
                'class': 'w-full border border-gray-300 rounded px-3 py-2 bg-white focus:ring-2 focus:ring-blue-500 focus:outline-none'
            }),
            # We use HiddenInput for amount because the legacy template uses a separate 
            # JS-controlled input (amount_display) to handle currency formatting (commas),
            # and updates this hidden field with the raw numeric value.
            'amount': forms.HiddenInput(attrs={
                'id': 'amount' 
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full border border-gray-300 rounded px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:outline-none',
                'rows': 3,
                'placeholder': 'Add any additional notes or description...'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Dynamic Year Range: Current Year +/- 5 years
        import datetime
        current_year = datetime.datetime.now().year
        # Generates: 2020 to 2030 (if current is 2025)
        year_choices = [(str(y), str(y)) for y in range(current_year - 5, current_year + 6)]
        
        self.fields['fiscal_year'].widget.choices = [('', '-- Select Year --')] + year_choices
