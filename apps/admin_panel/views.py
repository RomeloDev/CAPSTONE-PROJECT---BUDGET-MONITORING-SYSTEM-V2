from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView, ListView, DetailView
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.utils.decorators import method_decorator
from datetime import datetime
from apps.user_accounts.models import User
from apps.budgets.models import (
    ApprovedBudget, 
    BudgetAllocation, 
    DepartmentPRE, 
    PurchaseRequest, 
    ActivityDesign,
    RequestApproval,
    SystemNotification,
    DepartmentPREApprovedDocument
)
from django.contrib import messages
from apps.admin_panel.models import AuditTrail
from apps.budgets.models import ApprovedBudget, BudgetTransaction
from apps.budgets.forms import ApprovedBudgetForm
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required, user_passes_test
from .forms import BudgetAllocationForm, CustomUserCreationForm, CustomUserEditForm, ApprovedDocumentUploadForm
import json
from django.views.decorators.http import require_POST
from apps.admin_panel.utils import log_activity

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

@method_decorator(login_required, name="dispatch")
class BudgetAllocationListView(ListView):
    model = BudgetAllocation
    template_name = 'admin_panel/budget_allocation.html'
    context_object_name = 'allocations'
    paginate_by = 10
    
    def get_queryset(self):
        """"Handle Filtering and Search"""
        queryset = super().get_queryset().select_related('approved_budget', 'end_user').filter(is_active=True).order_by('-allocated_at')
        
        # Filters
        self.fiscal_year = self.request.GET.get('fiscal_year')
        self.mfo = self.request.GET.get('mfo')
        self.department = self.request.GET.get('department')
        self.search = self.request.GET.get('search')
        self.summary_year = self.request.GET.get('summary_year', 'all')
        
        if self.fiscal_year:
            queryset = queryset.filter(approved_budget__fiscal_year=self.fiscal_year)
            
        if self.mfo:
            queryset = queryset.filter(end_user__mfo=self.mfo)
            
        if self.department:
            queryset = queryset.filter(department__icontains=self.department)
            
        if self.search:
            queryset = queryset.filter(
                Q(end_user__first_name__icontains=self.search) |
                Q(end_user__last_name__icontains=self.search) |
                Q(end_user__username__icontains=self.search)
            )
            
        return queryset
    
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()
        
        # Statistics
        context['total_allocated'] = queryset.aggregate(Sum('allocated_amount'))['allocated_amount__sum'] or 0
        context['total_remaining'] = queryset.aggregate(Sum('remaining_balance'))['remaining_balance__sum'] or 0
        context['total_departments'] = queryset.values('department').distinct().count()
        
        total_used = context['total_allocated'] - context['total_remaining']
        context['utilization_rate'] = (total_used / context['total_allocated'] * 100) if context['total_allocated'] > 0 else 0
        
        # Dropdowns
        context['available_years'] = ApprovedBudget.objects.values_list('fiscal_year', flat=True).distinct().order_by('-fiscal_year')
        context['mfos'] = User.objects.values_list('mfo', flat=True).distinct().exclude(mfo__isnull=True).exclude(mfo='')
        context['approved_budgets'] = ApprovedBudget.objects.filter(is_active=True, remaining_budget__gt=0)
        
        context['selected_year'] = self.summary_year
        return context
    
    def post(self, request, *args, **kwargs):
        """"Handle Create and Edit Actions"""
        action = request.POST.get('action')
        
        if action == 'edit':
            return self.handle_edit(request)
        else:
            return self.handle_create(request)
        
    def handle_create(self, request):
        form = BudgetAllocationForm(request.POST)
        
        if form.is_valid():
            try:
                allocation = form.save(commit=False)
                allocation.end_user = form.end_user
                allocation.department = form.end_user.department
                allocation.remaining_balance = allocation.allocated_amount
                allocation.save()
                # Update Approved Budget
                approved_budget = allocation.approved_budget
                approved_budget.remaining_budget -= allocation.allocated_amount
                approved_budget.save()
                
                messages.success(request, "Budget allocated successfully.")
            except Exception as e:
                messages.error(request, f"Error saving allocation: {e}")
                
        else:
            for error in form.errors.values():
                messages.error(request, error)
                
        return redirect('budget_allocation')
    
    def handle_edit(self, request):
        allocation_id = request.POST.get('allocation_id')
        allocation = get_object_or_404(BudgetAllocation, id=allocation_id)
        
        # Pass instance to form for update context
        form = BudgetAllocationForm(request.POST, instance=allocation)
        
        if form.is_valid():
            try:
                new_amount = form.cleaned_data['allocated_amount']
                old_amount = allocation.allocated_amount # Pre-update value (from DB)
                
                # Logic to update parent budget based on difference
                difference = new_amount - old_amount
                approved_budget = allocation.approved_budget
                
                if difference != 0:
                    approved_budget.remaining_budget -= difference
                    approved_budget.save()
                # Save allocation with new amount
                allocation = form.save(commit=False)
                allocation.remaining_balance = new_amount - allocation.get_total_used()
                allocation.save()
                
                messages.success(request, "Budget allocation updated successfully.")
            except Exception as e:
                messages.error(request, f"Error updating: {e}")
        else:
            for error in form.errors.values():
                messages.error(request, error)
                
        return redirect('budget_allocation')
    
    
@login_required
def get_users_by_mfo(request):
    """API: Get users for MFO dropdown"""
    mfo = request.GET.get('mfo')
    users = User.objects.filter(mfo=mfo, is_active=True).values('id', 'fullname', 'department')
    data = [{'id': u['id'], 'name': f"{u['fullname']} ({u['department']})"} for u in users]
    return JsonResponse({'users': data})
@login_required
def budget_allocation_detail(request, pk):
    """API: Get allocation details for modal"""
    allocation = get_object_or_404(BudgetAllocation, pk=pk)
    
    # helper to safely get user attributes
    user = allocation.end_user
    
    data = {
        'id': allocation.id,
        # Approved Budget Info
        'budget_title': allocation.approved_budget.title,
        'fiscal_year': allocation.approved_budget.fiscal_year,
        'approved_budget_total': float(allocation.approved_budget.amount),
        'approved_budget_remaining': float(allocation.approved_budget.remaining_budget),
        
        # User Info
        'end_user_name': user.get_full_name(),
        'username': user.username,
        'email': user.email,
        # Use getattr for custom fields if they might not exist or be empty
        'mfo': getattr(user, 'mfo', 'N/A'), 
        'department': allocation.department, # BudgetAllocation has its own department field
        'position': getattr(user, 'position', 'N/A'),
        
        # Financials
        'allocated_amount': float(allocation.allocated_amount),
        'remaining_balance': float(allocation.remaining_balance),
        
        # Usage breakdown
        'pre_used': float(allocation.pre_amount_used),
        'pr_used': float(allocation.pr_amount_used),
        'ad_used': float(allocation.ad_amount_used),
        'total_used': float(allocation.get_total_used()),
        
        # Meta
        'allocated_at': allocation.allocated_at.strftime('%Y-%m-%d %H:%M'),
    }
    
    return JsonResponse(data)

# Users Management Views and API
class ClientAccountsListView(ListView):
    model = User
    template_name = 'admin_panel/client_accounts.html'
    context_object_name = 'users'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = User.objects.filter(is_superuser=False, is_admin=False).order_by('-created_at')
        
        # Filtering
        self.department = self.request.GET.get('department')
        self.role = self.request.GET.get('role')
        self.status = self.request.GET.get('status')
        self.search = self.request.GET.get('search')
        
        if self.department:
            queryset = queryset.filter(department=self.department)
        if self.role == 'approving_officer':
            queryset = queryset.filter(is_approving_officer=True)
        elif self.role == 'end_user':
            queryset = queryset.filter(is_approving_officer=False)
        if self.status == 'active':
            queryset = queryset.filter(is_active=True)
        elif self.status == 'inactive':
            queryset = queryset.filter(is_active=False)
        if self.search:
            queryset = queryset.filter(
                Q(fullname__icontains=self.search) | 
                Q(username__icontains=self.search) |
                Q(email__icontains=self.search)
            )
        return queryset
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset() # Current filtered
        all_users = User.objects.filter(is_superuser=False, is_admin=False)
        
        # Statistics
        context['total_users'] = all_users.count()
        context['active_users'] = all_users.filter(is_active=True).count()
        context['inactive_users'] = all_users.filter(is_active=False).count()
        context['end_user_count'] = all_users.filter(is_approving_officer=False).count()
        
        # Filters
        context['departments'] = User.objects.values_list('department', flat=True).distinct()
        
        return context
    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        
        if action == 'create':
            form = CustomUserCreationForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, "User created successfully.")
            else:
                for error in form.errors.values():
                    messages.error(request, error)
                    
        elif action == 'edit':
            user_id = request.POST.get('user_id')
            user = get_object_or_404(User, id=user_id)
            form = CustomUserEditForm(request.POST, instance=user)
            if form.is_valid():
                form.save()
                messages.success(request, "User updated successfully.")
            else:
                messages.error(request, "Error updating user.")
                
        return redirect('client_accounts')
    
@login_required
def user_detail(request, pk):
    user = get_object_or_404(User, pk=pk)
    data = {
        'id': user.id,
        'fullname': user.fullname,
        'username': user.username,
        'email': user.email,
        'department': user.department,
        'mfo': user.mfo,
        'position': user.position,
        'is_active': user.is_active,
        'is_approving_officer': user.is_approving_officer,
        'created_at': user.created_at.strftime('%Y-%m-%d'),
        'last_login': user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else 'Never'
    }
    return JsonResponse(data)
@login_required
@require_POST
def toggle_user_status(request, pk):
    user = get_object_or_404(User, pk=pk)
    # Check permission (cannot deactivate self)
    if user == request.user:
        return JsonResponse({'success': False, 'message': 'Cannot change your own status.'})
        
    user.is_active = not user.is_active
    user.save()
    status = "activated" if user.is_active else "deactivated"
    return JsonResponse({'success': True, 'message': f"User {status} successfully."})
@login_required
@require_POST
def bulk_user_action(request):
    try:
        data = json.loads(request.body)
        action = data.get('action')
        user_ids = data.get('user_ids', [])
        
        if not user_ids:
            return JsonResponse({'success': False, 'message': 'No users selected.'})
            
        users = User.objects.filter(id__in=user_ids)
        
        if action == 'activate':
            users.update(is_active=True)
            message = f"{users.count()} users activated."
        elif action == 'deactivate':
            # Prevent self-deactivation if ID in list
            users.exclude(id=request.user.id).update(is_active=False)
            message = f"{users.count()} users deactivated."
        else:
            return JsonResponse({'success': False, 'message': 'Invalid action.'})
            
        return JsonResponse({'success': True, 'message': message})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})
    
    
class AuditTrailListView(LoginRequiredMixin, ListView):
    template_name = 'admin_panel/audit_trail.html'
    paginate_by = 20
    context_object_name = 'page_obj'
    def get_queryset(self):
        tab = self.request.GET.get('tab', 'activity')
        
        if tab == 'budget':
            # === BUDGET CHANGES TAB ===
            queryset = BudgetTransaction.objects.select_related('allocation', 'allocation__end_user', 'created_by').all()
            
            # Filter: Department
            dept = self.request.GET.get('department')
            if dept:
                queryset = queryset.filter(allocation__department=dept)
                
            # Filter: Transaction Type
            trans_type = self.request.GET.get('transaction_type')
            if trans_type:
                queryset = queryset.filter(transaction_type=trans_type)
                
        else:
            # === USER ACTIVITY TAB (Default) ===
            queryset = AuditTrail.objects.select_related('user').all()
            
            # Filter: Department (via User)
            dept = self.request.GET.get('department')
            if dept:
                queryset = queryset.filter(user__department=dept)
                
            # Filter: Action
            action = self.request.GET.get('action')
            if action:
                queryset = queryset.filter(action=action)
        # Common Filter: Date Range
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date) if tab == 'budget' else queryset.filter(timestamp__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date) if tab == 'budget' else queryset.filter(timestamp__date__lte=end_date)
            
        return queryset
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_tab'] = self.request.GET.get('tab', 'activity')
        
        # Context for filters
        context['departments'] = User.objects.values_list('department', flat=True).distinct()
        
        if context['active_tab'] == 'activity':
            context['action_choices'] = AuditTrail.ACTION_CHOICES
        else:
            context['transaction_types'] = BudgetTransaction.TRANSACTION_TYPES
            
        return context
    
    
class PRERequestListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = DepartmentPRE
    template_name = 'admin_panel/pre_list.html'
    context_object_name = 'pres'
    paginate_by = 10
    ordering = ['-submitted_at']
    def test_func(self):
        return self.request.user.is_superuser or self.request.user.is_staff
    def get_queryset(self):
        queryset = super().get_queryset().exclude(status='Draft').select_related(
            'submitted_by', 
            'budget_allocation',
            'budget_allocation__approved_budget'
        )
        # --- Filtering ---
        search_query = self.request.GET.get('search', '')
        department = self.request.GET.get('department', '')
        status = self.request.GET.get('status', '')
        date_from = self.request.GET.get('date_from', '')
        date_to = self.request.GET.get('date_to', '')
        # Search (ID prefix or Submitter Name)
        if search_query:
            queryset = queryset.filter(
                Q(id__icontains=search_query) |
                Q(submitted_by__first_name__icontains=search_query) |
                Q(submitted_by__last_name__icontains=search_query) |
                Q(submitted_by__username__icontains=search_query)
            )
        if department:
            queryset = queryset.filter(department=department)
        if status:
            queryset = queryset.filter(status=status)
        if date_from:
            queryset = queryset.filter(submitted_at__date__gte=date_from)
        
        if date_to:
            queryset = queryset.filter(submitted_at__date__lte=date_to)
        return queryset
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # --- Stats Counters ---
        # We calculate these on the FULL dataset, not just the filtered page
        all_pres = DepartmentPRE.objects.all()
        
        context['stats'] = {
            'total': all_pres.exclude(status='Draft').count(),
            'pending': all_pres.filter(status='Pending').count(),
            'approved': all_pres.filter(status='Approved').count(),
            'rejected': all_pres.filter(status='Rejected').count(),
        }
        # --- Filter Options ---
        # Get distinct departments from existing PREs (since DeptStation model doesn't exist)
        context['departments'] = DepartmentPRE.objects.values_list('department', flat=True).distinct().order_by('department')
        
        # Status choices from model
        context['status_choices'] = DepartmentPRE.STATUS_CHOICES
        return context
    
    
class PREDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = DepartmentPRE
    template_name = 'admin_panel/pre_detail.html'
    context_object_name = 'pre'
    
    def test_func(self):
        return self.request.user.is_superuser or self.request.user.is_staff
    def get_queryset(self):
        # Optimize query to fetch related data in one go
        return super().get_queryset().select_related(
            'submitted_by',
            'budget_allocation',
            'budget_allocation__approved_budget'
        ).prefetch_related(
            'line_items__category',
            'line_items__subcategory',
            'supporting_documents',      
            'signed_approved_documents'
        )
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pre = self.object
        
        # 1. Approval History
        # If RequestApproval model exists, fetch history
        if RequestApproval:
             context['approval_history'] = RequestApproval.objects.filter(
                content_type='pre',
                object_id=pre.id
            ).select_related('approved_by').order_by('-approved_at')
        
        # 2. Supporting Documents
        # If created in previous migration, fetch them
        if hasattr(pre, 'supporting_documents'):
            context['supporting_documents'] = pre.supporting_documents.all().order_by('-uploaded_at')
        # 3. Budget Tracking Breakdown (The Complex Part)
        # Calculates consumption for PRs and ADs per quarter
        line_items_with_breakdown = []
        
        # Iterate over all line items
        for item in pre.line_items.all():
            item_data = {
                'item': item,
                'quarters': []
            }
            # Generate breakdown for each quarter
            # This relies on item.get_quarter_breakdown() method on PRELineItem model
            for quarter in ['Q1', 'Q2', 'Q3', 'Q4']:
                if hasattr(item, 'get_quarter_breakdown'):
                    breakdown = item.get_quarter_breakdown(quarter)
                    item_data['quarters'].append(breakdown)
            
            line_items_with_breakdown.append(item_data)
            
        context['line_items_with_breakdown'] = line_items_with_breakdown
        
        return context
    
    
@login_required
@user_passes_test(lambda u: u.is_staff)
def admin_handle_pre_action(request, pre_id):
    if request.method != 'POST':
        return redirect('admin_pre_list')
    
    pre = get_object_or_404(DepartmentPRE, id=pre_id)
    action = request.POST.get('action')
    department_name = pre.department  # Store for message
    
    if action == 'approve':
        if pre.status == 'Pending':
            pre.status = 'Partially Approved'
            pre.partially_approved_at = timezone.now()
            pre.save()
            
            # Create Approval Record
            RequestApproval.objects.create(
                content_type='pre',
                object_id=pre.id,
                approved_by=request.user,
                approval_level='partial',
                comments=request.POST.get('comments', '')
            )
            
            # Send Notification
            SystemNotification.objects.create(
                recipient=pre.submitted_by,
                title='PRE Partially Approved',
                message=f'Your PRE for {department_name} has been partially approved.',
                content_type='pre',
                object_id=pre.id
            )
            
            messages.success(request, f'PRE {str(pre.id)[:8]} has been partially approved.')
        else:
            messages.warning(request, 'This PRE cannot be approved in its current status.')
            
    elif action == 'reject':
        if pre.status == 'Pending':
            reason = request.POST.get('reason', 'No reason provided')
            pre.status = 'Rejected'
            pre.rejection_reason = reason
            pre.save()
            
            # Create Rejection Record
            RequestApproval.objects.create(
                content_type='pre',
                object_id=pre.id,
                approved_by=request.user,
                approval_level='rejected',
                comments=reason
            )
            
            # Send Notification
            SystemNotification.objects.create(
                recipient=pre.submitted_by,
                title='PRE Rejected',
                message=f'Your PRE for {department_name} has been rejected. Reason: {reason}',
                content_type='pre',
                object_id=pre.id
            )
            
            messages.success(request, 'PRE has been rejected.')
        else:
            messages.warning(request, 'This PRE cannot be rejected in its current status.')
            
    return redirect('admin_pre_detail', pk=pre.id) # Ensure this matches your detail view URL name


@login_required
@user_passes_test(lambda u: u.is_staff)
def admin_verify_and_approve_pre(request, pre_id):
    if request.method != 'POST':
        return redirect('admin_pre_detail', pk=pre_id)
    pre = get_object_or_404(DepartmentPRE, id=pre_id)
    action = request.POST.get('action')
    comment = request.POST.get('reason', '') # Reuse 'reason' field for rejection comments
    if pre.status != 'Awaiting Admin Verification':
        messages.error(request, f'Cannot verify PRE. Current status: {pre.status}')
        return redirect('admin_pre_detail', pk=pre.id)
    if action == 'approve':
        pre.status = 'Approved'
        pre.awaiting_verification = False
        pre.final_approved_at = timezone.now() # Use appropriate timestamp field
        pre.admin_notes = comment
        pre.save()
        # Update budget consumption (Crucial!)
        if pre.budget_allocation:
            # Assuming budget_allocation has logic to update balances
            # pre.budget_allocation.update_balance(pre.total_amount) 
            pass 
        RequestApproval.objects.create(
            content_type='pre',
            object_id=pre.id,
            approved_by=request.user,
            approval_level='final',
            comments='Documents verified and approved.'
        )
        
        SystemNotification.objects.create(
            recipient=pre.submitted_by,
            title='PRE Verified & Approved',
            message=f'Your signed documents for PRE {str(pre.id)[:8]} have been verified. Request is now fully approved.',
            content_type='pre',
            object_id=pre.id
        )
        messages.success(request, 'PRE verified and fully approved!')
    elif action == 'reject':
        # Revert to Partially Approved, require re-upload
        pre.status = 'Partially Approved'
        pre.awaiting_verification = False
        pre.rejection_reason = comment
        pre.save()
        
        # Ideally, delete the invalid documents here if you have a relation to them
        # pre.signed_documents.all().delete()
        RequestApproval.objects.create(
            content_type='pre',
            object_id=pre.id,
            approved_by=request.user,
            approval_level='verification_rejected',
            comments=comment
        )
        
        SystemNotification.objects.create(
            recipient=pre.submitted_by,
            title='Documents Rejected',
            message=f'The signed documents for PRE {str(pre.id)[:8]} were rejected. Please check comments and re-upload.',
            content_type='pre',
            object_id=pre.id
        )
        messages.warning(request, 'Verification rejected. User has been notified to re-upload.')
    return redirect('admin_pre_detail', pk=pre.id)


@login_required
@user_passes_test(lambda u: u.is_staff)
def admin_upload_approved_document(request, pre_id):
    pre = get_object_or_404(DepartmentPRE, id=pre_id)
    
    if request.method == 'POST':
        # Simply handling file manually for simplicity, or use a Form
        if 'approved_document' in request.FILES:
            file = request.FILES['approved_document']
            pre.approved_documents = file # Adjust field name to match your model
            pre.status = 'Approved'
            pre.final_approved_at = timezone.now()
            pre.save()
            
            RequestApproval.objects.create(
                content_type='pre',
                object_id=pre.id,
                approved_by=request.user,
                approval_level='final',
                comments='Admin manually uploaded signed document.'
            )
            
            messages.success(request, 'Document uploaded and PRE fully approved.')
            return redirect('admin_pre_detail', pk=pre.id)
        else:
            messages.error(request, 'No file selected.')
            
    return render(request, 'admin_panel/upload_approved_doc.html', {'pre': pre})

class AdminPRListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = PurchaseRequest
    template_name = 'admin_panel/pr_list.html'
    context_object_name = 'purchase_requests'
    paginate_by = 20 # Optional but recommended
    
    def test_func(self):
        return self.request.user.is_superuser or self.request.user.is_staff # Adjust permission logic
    def get_queryset(self):
        queryset = PurchaseRequest.objects.select_related('submitted_by', 'department').all().order_by('-created_at')
        
        # 1. Year Filter (Default to current year or 'all'?)
        year = self.request.GET.get('summary_year')
        if year and year != 'all':
            queryset = queryset.filter(created_at__year=year)
            
        # 2. Department Filter
        dept = self.request.GET.get('department')
        if dept:
            queryset = queryset.filter(department__name=dept) # Assuming dept name passed
            
        # 3. Status Filter
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
            
        return queryset
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Base Queryset for Stats (Separate from pagination, but usually respects Year filter)
        stats_qs = PurchaseRequest.objects.all()
        year = self.request.GET.get('summary_year')
        if year and year != 'all':
            stats_qs = stats_qs.filter(created_at__year=year)
            
        # Aggregation
        stats = stats_qs.aggregate(
            total=Count('id'),
            pending=Count('id', filter=Q(status='Pending')),
            partially_approved=Count('id', filter=Q(status='Partially Approved')),
            approved=Count('id', filter=Q(status='Approved')),
            rejected=Count('id', filter=Q(status='Rejected')),
        )
        context['status_counts'] = stats
        
        # Filters Data
        context['available_years'] = PurchaseRequest.objects.dates('created_at', 'year').distinct()
        
        # If Department is a CharField, get distinct values:
        context['departments'] = PurchaseRequest.objects.values_list('department', flat=True).distinct().order_by('department') 
        # OR if you have a Department model, use Department.objects.all()
        
        context['selected_year'] = year if year else 'all'
        context['current_year'] = timezone.now().year
        context['status_choices'] = PurchaseRequest.STATUS_CHOICES # Ensure this exists in Model
        
        return context
    
@require_POST
def handle_pr_action(request, pr_id):
    pr = get_object_or_404(PurchaseRequest, id=pr_id)
    action = request.POST.get('action')
    
    if action == 'approve':
        # Logic for Approval
        # 1. Check if status is valid for approval
        if pr.status == 'Pending':
            # Initial Approval -> Move to 'Partially Approved' to allow User to upload signed docs
            pr.status = 'Partially Approved'
            pr.save()
            messages.success(request, f"PR {pr.pr_number} successfully approved! It is now 'Partially Approved' and awaiting user signature.")
        
        elif pr.status == 'Awaiting Admin Verification':
             # Final Approval -> Move to 'Approved'
            pr.status = 'Approved'
            pr.save()
            messages.success(request, f"PR {pr.pr_number} has been fully APPROVED.")
            
        else:
             messages.warning(request, f"PR {pr.pr_number} cannot be approved from its current status: {pr.status}")
    elif action == 'reject':
        # Logic for Rejection
        # Deduct/Release budget is handled automatically because 'Rejected' status 
        # is excluded from the 'total_used' aggregation in reports/views.
        pr.status = 'Rejected'
        pr.save()
        messages.error(request, f"PR {pr.pr_number} has been rejected.")
        
    return redirect('admin_pr_list')


class AdminPRListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = PurchaseRequest
    template_name = 'admin_panel/pr_list.html'
    context_object_name = 'purchase_requests'
    paginate_by = 20
    
    def test_func(self):
        return self.request.user.is_superuser or self.request.user.is_staff

    def get_queryset(self):
        # FIX: Removed 'department' from select_related as it is a CharField
        queryset = PurchaseRequest.objects.select_related('submitted_by').all().order_by('-created_at')
        
        # 1. Year Filter
        year = self.request.GET.get('summary_year')
        if year and year != 'all':
            queryset = queryset.filter(created_at__year=year)
            
        # 2. Department Filter
        dept = self.request.GET.get('department')
        if dept:
            queryset = queryset.filter(department=dept)
            
        # 3. Status Filter
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
            
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Base Queryset for Stats
        stats_qs = PurchaseRequest.objects.all()
        year = self.request.GET.get('summary_year')
        if year and year != 'all':
            stats_qs = stats_qs.filter(created_at__year=year)
            
        # Aggregation
        stats = stats_qs.aggregate(
            total=Count('id'),
            pending=Count('id', filter=Q(status='Pending')),
            partially_approved=Count('id', filter=Q(status='Partially Approved')),
            approved=Count('id', filter=Q(status='Approved')),
            rejected=Count('id', filter=Q(status='Rejected')),
        )
        context['status_counts'] = stats
        
        # Filters Data
        context['available_years'] = PurchaseRequest.objects.dates('created_at', 'year').distinct()
        
        # Get distinct department names
        context['departments'] = PurchaseRequest.objects.values_list('department', flat=True).distinct().order_by('department') 
        
        context['selected_year'] = year if year else 'all'
        context['current_year'] = timezone.now().year
        context['status_choices'] = PurchaseRequest.STATUS_CHOICES
        
        return context

@require_POST
def handle_pr_action(request, pr_id):
    pr = get_object_or_404(PurchaseRequest, id=pr_id)
    action = request.POST.get('action')
    
    if action == 'approve':
        if pr.status == 'Pending':
            pr.status = 'Partially Approved'
            pr.save()
            messages.success(request, f"PR {pr.pr_number} successfully approved! It is now 'Partially Approved'.")
        
        elif pr.status == 'Awaiting Admin Verification':
            pr.status = 'Approved'
            pr.save()
            messages.success(request, f"PR {pr.pr_number} has been fully APPROVED.")
            
        else:
             messages.warning(request, f"PR {pr.pr_number} cannot be approved from its current status: {pr.status}")

    elif action == 'reject':
        pr.status = 'Rejected'
        pr.save()
        messages.error(request, f"PR {pr.pr_number} has been rejected.")
        
    return redirect('admin_pr_list')
    
class AdminPRDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = PurchaseRequest
    template_name = 'admin_panel/pr_detail.html'
    context_object_name = 'pr'
    pk_url_kwarg = 'pr_id'
    
    def test_func(self):
        return self.request.user.is_superuser or self.request.user.is_staff
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pr = self.object
        
        # 1. Budget Allocation Info
        # Retrieve the relevant allocation if it exists
        if pr.budget_allocation:
             context['allocation'] = pr.budget_allocation
             # If you have PRE Line Item info, it might be accessible via the allocation or directly if linked
             # context['pre_line_item'] = pr.source_line_item 
        
        return context
    
@require_POST
@login_required
def admin_verify_and_approve_pr(request, pr_id):
    """
    Handles the 'Verify & Approve' or 'Reject Verification' actions 
    for PRs in the 'Awaiting Admin Verification' state.
    """
    pr = get_object_or_404(PurchaseRequest, id=pr_id)
    
    # Security Check
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Unauthorized access.")
        return redirect('admin_pr_list')
    action = request.POST.get('action')
    comment = request.POST.get('comment', '')
    
    if action == 'approve':
        # 1. Verify & Approve
        # Transitions state from 'Awaiting Admin Verification' -> 'Approved'
        pr.status = 'Approved'
        pr.final_approved_at = timezone.now()
        pr.admin_approved_by = request.user
        
        # Store optional notes if you have a field for it, e.g. 'admin_notes'
        # pr.admin_notes = comment 
        
        pr.save()
        
        # Update Budget Allocation Usage
        pr.update_budget_usage()
        
        messages.success(request, f"PR {pr.pr_number} has been verified and fully APPROVED.")
        
    elif action == 'reject':
        # 2. Reject Verification
        # Transitions state: 'Awaiting Admin Verification' -> 'Partially Approved'
        # This sends it back to the user to fix/re-upload documents.
        reason = request.POST.get('reason', 'Verification failed.')
        
        pr.status = 'Partially Approved' 
        # pr.admin_notes = f"Verification Rejected: {reason}" # Optional
        pr.save()
        
        messages.warning(request, f"Verification rejected. PR returned to user for correction. Reason: {reason}")
        
    return redirect('admin_pr_detail', pr_id=pr.id)