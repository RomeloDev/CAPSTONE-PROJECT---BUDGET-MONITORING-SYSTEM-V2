from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.budgets.models import ApprovedBudget
from apps.budgets.services import archive_budget_cascade

class Command(BaseCommand):
    help = 'Archives ApprovedBudget and related documents for past fiscal years'

    def handle(self, *args, **options):
        # Determine strict "Past Year" threshold
        # If current date is Jan 1, 2026, then 2025 and older are past coverage.
        current_year = timezone.now().year
        
        self.stdout.write(f"Checking for budgets older than {current_year}...")
        
        # Fetch active budgets
        budgets = ApprovedBudget.objects.filter(is_archived=False)
        count = 0
        
        for budget in budgets:
            try:
                # Handle varying formats like "2023", "2023-2024"
                # We assume the start year is the primary indicator
                fy_start_year = int(budget.fiscal_year[:4])
                
                if fy_start_year < current_year:
                    self.stdout.write(f"Archiving Budget: {budget.title} ({budget.fiscal_year})...")
                    archive_budget_cascade(budget.id, archive_type='FISCAL_YEAR')
                    count += 1
                    
            except (ValueError, IndexError):
                self.stdout.write(self.style.WARNING(f"Skipping budget with invalid fiscal year format: {budget.fiscal_year}"))
                continue

        if count > 0:
            self.stdout.write(self.style.SUCCESS(f"Successfully archived {count} past fiscal year budgets."))
        else:
            self.stdout.write(self.style.SUCCESS("No past fiscal year budgets found to archive."))
