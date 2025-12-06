from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import datetime
from django.views.generic import ListView
from apps.user_accounts.models import User
from apps.budgets.models import (
    ApprovedBudget, 
    BudgetAllocation, 
    DepartmentPRE, 
    PurchaseRequest, 
    ActivityDesign
)
from django.contrib import messages
from apps.admin_panel.models import AuditTrail
from apps.budgets.models import ApprovedBudget
from apps.budgets.forms import ApprovedBudgetForm
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required

class AdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Dashboard for Budget Officers/Admins"""
    template_name = 'admin_panel/dashboard.html'

    def test_func(self):
        return self.request.user.is_superuser or self.request.user.is_staff

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # --- Date & Time Setup ---
        now = timezone.now()
        current_year = now.year
        selected_year = self.request.GET.get('year', str(current_year))
        
        context['current_time'] = now
        context['current_year'] = current_year
        context['selected_year'] = selected_year
        
        # Get available years for filter
        available_years = ApprovedBudget.objects.values_list('fiscal_year', flat=True).distinct().order_by('-fiscal_year')
        context['available_years'] = available_years

        # --- 1. User Stats ---
        # Count active end users (excluding superusers/staff if desired, or all active)
        end_users_total = User.objects.filter(is_active=True).count()
        context['end_users_total'] = end_users_total
        
        # Simple trend (mocked for now, or compare to last month if we tracked creation date)
        # Assuming 'up' for positive vibes
        context['user_trend'] = 'up' 

        # --- 2. Budget Stats ---
        # Filter by selected year if not 'all'
        budget_query = ApprovedBudget.objects.filter(is_active=True)
        if selected_year != 'all':
            budget_query = budget_query.filter(fiscal_year=selected_year)
            
        total_budget = budget_query.aggregate(total=Sum('amount'))['total'] or 0
        context['total_budget'] = total_budget
        context['budget_trend'] = 'up' # Placeholder

        # --- 3. Request Statuses (Pending vs Approved) ---
        # We look at all request types: PRE, PR, AD
        
        # Pending Counts
        pending_pre = DepartmentPRE.objects.filter(status='Pending').count()
        pending_pr = PurchaseRequest.objects.filter(status='Pending').count()
        pending_ad = ActivityDesign.objects.filter(status='Pending').count()
        
        total_pending = pending_pre + pending_pr + pending_ad
        context['total_pending_realignment_request'] = total_pending # Using legacy variable name
        context['pending_trend'] = 'down' if total_pending < 5 else 'up'

        # Approved Counts
        approved_pre = DepartmentPRE.objects.filter(status='Approved').count()
        approved_pr = PurchaseRequest.objects.filter(status='Approved').count()
        approved_ad = ActivityDesign.objects.filter(status='Approved').count()
        
        total_approved = approved_pre + approved_pr + approved_ad
        context['total_approved_realignment_request'] = total_approved # Using legacy variable name
        context['approved_trend'] = 'up'

        # --- 4. Department Metrics ---
        # Get allocations for the selected year (via ApprovedBudget linkage)
        allocations = BudgetAllocation.objects.all()
        if selected_year != 'all':
            allocations = allocations.filter(approved_budget__fiscal_year=selected_year)
            
        # Group by department
        dept_stats = allocations.values('department').annotate(
            total_allocated=Sum('allocated_amount'),
            spent=Sum('pr_amount_used') + Sum('ad_amount_used'),
            remaining_budget=Sum('remaining_balance')
        ).order_by('-total_allocated')
        
        context['budget_allocated'] = dept_stats # For the table
        context['active_departments'] = dept_stats.count()
        
        # Calculate Low Budget Alerts (departments with < 10% remaining)
        low_budget_count = 0
        total_utilization = 0
        dept_count = 0
        
        # Prepare data for Chart.js
        dept_labels = []
        dept_allocated_data = []
        dept_spent_data = []
        dept_remaining_data = []
        
        for stat in dept_stats:
            allocated = stat['total_allocated'] or 0
            remaining = stat['remaining_budget'] or 0
            
            if allocated > 0:
                percentage = (remaining / allocated) * 100
                if percentage < 10:
                    low_budget_count += 1
                
                utilization = ((allocated - remaining) / allocated) * 100
                total_utilization += utilization
                dept_count += 1
            
            # Chart Data (Top 10 departments to avoid overcrowding)
            if len(dept_labels) < 10:
                dept_labels.append(stat['department'])
                dept_allocated_data.append(float(allocated))
                dept_spent_data.append(float(stat['spent'] or 0))
                dept_remaining_data.append(float(remaining))

        context['low_budget_depts'] = low_budget_count
        context['avg_utilization'] = round(total_utilization / dept_count, 1) if dept_count > 0 else 0
        
        # Pass JSON data for charts
        context['dept_labels'] = dept_labels
        context['dept_allocated'] = dept_allocated_data
        context['dept_spent'] = dept_spent_data
        context['dept_remaining'] = dept_remaining_data

        # --- 5. Recent Activity (Audit Trail) ---
        recent_activities = AuditTrail.objects.select_related('user').order_by('-timestamp')[:10]
        context['recent_activities'] = recent_activities

        return context
    
class ApprovedBudgetListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = ApprovedBudget
    template_name = 'admin_panel/approved_budget.html'
    context_object_name = 'approved_budgets'
    paginate_by = 10
    
    def test_func(self):
        return self.request.user.is_superuser or self.request.user.is_staff
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        year = self.request.GET.get('summary_year')
        if year and year != 'all':
            queryset = queryset.filter(fiscal_year=year)
            
        # GET Parameters from the URL
        # 'summary_year' is the Card Filter, 'fiscal_year' is from the filter Modal
        summary_year = self.request.GET.get('summary_year')
        fiscal_year = self.request.GET.get('fiscal_year')
        amount_min = self.request.GET.get('amount_min')
        amount_max = self.request.GET.get('amount_max')
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        search = self.request.GET.get('search')
        
        # Apply Filters
        if fiscal_year:
            queryset = queryset.filter(fiscal_year=fiscal_year)
        elif summary_year and summary_year != 'all':
            queryset = queryset.filter(fiscal_year=summary_year)
            
        # Amount Range
        if amount_min:
            queryset = queryset.filter(amount__gte=amount_min)
        if amount_max:
            queryset = queryset.filter(amount__lte=amount_max)
            
        # Date Range
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)
        
        # Search (Title or Description)
        if search:
            queryset =  queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search)
            )
            
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # --- 1. Pass the Form ---
        # We pass the form to the context so it can be rendered in the modal
        context['form'] = ApprovedBudgetForm()
        
        # --- 2. Pass Summary Data ---
        # Calculate totals for the cards
        queryset = self.get_queryset()
        context['total_approved_budget'] = queryset.aggregate(Sum('amount'))['amount__sum'] or 0
        context['total_remaining_budget'] = queryset.aggregate(Sum('remaining_budget'))['remaining_budget__sum'] or 0
        context['total_budget_count'] = queryset.count()
        
        # Calculate utilization (example logic)
        if context['total_approved_budget'] > 0:
            used = context['total_approved_budget'] - context['total_remaining_budget']
            context['budget_utilization_rate'] = round((used / context['total_approved_budget']) * 100, 1)
        else:
            context['budget_utilization_rate'] = 0
            
            
        # --- 3. Pass Filter Options ---
        context['available_years'] = ApprovedBudget.objects.values_list('fiscal_year', flat=True).distinct().order_by('-fiscal_year')
        context['selected_year'] = self.request.GET.get('summary_year', 'all')
        
        return context
    def post(self, request, *args, **kwargs):
        # Check for 'action' hidden input to determine action
        action = request.POST.get('action')
        
        if action == 'edit':
            """Handle form submission for editing an existing budget"""
            budget_id = request.POST.get('budget_id')
            budget = get_object_or_404(ApprovedBudget, pk=budget_id)
            
            # Update Fields
            budget.title = request.POST.get('title')
            budget.fiscal_year = request.POST.get('fiscal_year')
            
            #Handle amount carefully (check if it changed, might affect logic)
            new_amount = request.POST.get('amount')
            if new_amount:
                # Calculate difference if you track remaining budget logic
                # For now, simplistic update:
                budget.amount = new_amount
            
            budget.description = request.POST.get('description')
            budget.save()
            
            # Handle NEW files (Append Them)
            files = request.FILES.getlist('supporting_documents')
            from apps.budgets.models import SupportingDocument
            for f in files:
                SupportingDocument.objects.create(
                    approved_budget=budget,
                    document=f,
                    uploaded_by=request.user,
                    file_name=f.name
                )
                
            messages.success(request, 'Budget updated successfully!')
            return redirect('approved_budget')
        
        else: 
            """Handle form submission for adding a new budget"""
            form = ApprovedBudgetForm(request.POST, request.FILES)
            if form.is_valid():
                try:
                    # 1. Start Validation: Check if files are uploaded (since it's required)
                    files = request.FILES.getlist('budget_files')
                    if not files:
                        messages.error(request, "Supporting Documents: At least one file is required.")
                        return redirect('approved_budget')

                    # 2. Save the Budget
                    budget = form.save(commit=False)
                    budget.created_by = request.user
                    budget.remaining_budget = budget.amount 
                    budget.save()
                    
                    # 3. Handle Multiple File Uploads
                    from apps.budgets.models import SupportingDocument
                    
                    for f in files:
                        SupportingDocument.objects.create(
                            approved_budget=budget,
                            document=f,
                            uploaded_by=request.user,
                            file_name=f.name, # Model auto-populates format/size in save()
                            description="Initial supporting document"
                        )
                    
                    messages.success(request, f'Approved Budget "{budget.title}" added successfully with {len(files)} document(s)!')
                    return redirect('approved_budget')
                except Exception as e:
                    # Catch unexpected server errors during save
                    messages.error(request, f'Error saving budget: {str(e)}')
                    return redirect('approved_budget')
            else:
                # Show specific form errors
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field.capitalize()}: {error}")
                return redirect('approved_budget')
        
@login_required
def approved_budget_detail(request, pk):
    """
    API endpoint to get budget details for modals
    """
    budget = get_object_or_404(ApprovedBudget, pk=pk)
    
    # Get associated documents
    documents = []
    for doc in budget.supporting_documents.all():
        documents.append({
            'name': doc.file_name,
            'url': doc.document.url,
            'size': f"{doc.file_size / 1024:.2f} KB" if doc.file_size else "N/A",
        })
    
    data = {
        'id': budget.id,
        'title': budget.title,
        'description': budget.description,
        'fiscal_year': budget.fiscal_year,
        'amount': float(budget.amount),
        'remaining_budget': float(budget.remaining_budget),
        'created_by': budget.created_by.get_full_name(),
        'created_at': budget.created_at.strftime('%Y-%m-%d %H:%M'),
        'documents': documents,
    }
    
    return JsonResponse(data)