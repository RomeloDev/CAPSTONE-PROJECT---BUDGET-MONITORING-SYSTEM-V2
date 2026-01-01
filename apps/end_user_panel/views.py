from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView, DetailView
from django.db.models import Sum, Q, Exists, OuterRef, F, Value, DecimalField
from django.db.models.functions import Coalesce
from django.contrib import messages
from django.views import View
from decimal import Decimal
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from django.contrib.auth.decorators import login_required, user_passes_test
from apps.budgets.models import (
    PurchaseRequest, 
    ActivityDesign, 
    BudgetAllocation, 
    DepartmentPRE, 
    DepartmentPRESupportingDocument, 
    PRELineItem,
    PRECategory,
    PRESubCategory,
    PREDraft,
    PREDraftSupportingDocument,
    DepartmentPREApprovedDocument,
    PurchaseRequestAllocation,
    ActivityDesignAllocation,
    PurchaseRequestSupportingDocument,
    PRDraft,
    PRDraftSupportingDocument,
    ActivityDesignSupportingDocument,
    PREBudgetRealignment,
    BudgetRealignmentSupportingDocument
)
from .forms import (
    PurchaseRequestDetailsForm, 
    PurchaseRequestSupportingDocForm, 
    PurchaseRequestUploadForm, 
    ActivityDesignUploadForm, 
    ActivityDesignSupportingDocForm, 
    ActivityDesignDetailsForm,
    PREBudgetRealignmentForm
)
from io import BytesIO
from PIL import Image
from django.core.files.base import ContentFile
from django.views.generic import FormView
# Note: PREDraft and PREDraftSupportingDocument are used for draft management
# DepartmentPRE is created only on final submission in PreviewPREView
from apps.end_user_panel.utils.pre_parser_dynamic import parse_pre_excel_dynamic
import json
import os
import uuid
from datetime import datetime
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_POST

class EndUserDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Dashboard for regular staff/end users"""
    template_name = 'end_user_panel/dashboard.html'
    
    def test_func(self):
        return self.request.user.is_staff == False or self.request.user.is_superuser == False

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['user'] = user
        
        # --- 1. Budget Stats ---
        allocations = BudgetAllocation.objects.filter(end_user=user)
        stats = allocations.aggregate(
            total_allocated=Sum('allocated_amount'),
            total_pr_used=Sum('pr_amount_used'),
            total_ad_used=Sum('ad_amount_used'),
            total_remaining=Sum('remaining_balance')
        )
        
        total_allocated = stats['total_allocated'] or 0
        total_used = (stats['total_pr_used'] or 0) + (stats['total_ad_used'] or 0)
        total_remaining = total_allocated - total_used or 0
        total_pr_used = stats['total_pr_used'] or 0
        total_ad_used = stats['total_ad_used'] or 0
        
        context['total_allocated'] = total_allocated
        context['total_used'] = total_used
        context['total_remaining'] = total_remaining
        context['total_pr_used'] = total_pr_used
        context['total_ad_used'] = total_ad_used
        
        # Calculate Percentages
        if total_allocated > 0:
            context['utilization_percentage'] = (total_used / total_allocated) * 100
            context['remaining_percentage'] = (total_remaining / total_allocated) * 100
        else:
            context['utilization_percentage'] = 0
            context['remaining_percentage'] = 0

        # --- 2. Document Counts ---
        # Active Documents (Total submitted)
        pre_count = DepartmentPRE.objects.filter(submitted_by=user).count()
        pr_count = PurchaseRequest.objects.filter(submitted_by=user).count()
        ad_count = ActivityDesign.objects.filter(submitted_by=user).count()
        
        context['pre_count'] = pre_count
        context['pr_count'] = pr_count
        context['ad_count'] = ad_count
        context['total_active_documents'] = pre_count + pr_count + ad_count

        # Pending Counts
        context['pending_pre_count'] = DepartmentPRE.objects.filter(submitted_by=user, status='Pending').count()
        context['pending_pr_count'] = PurchaseRequest.objects.filter(submitted_by=user, status='Pending').count()
        context['pending_ad_count'] = ActivityDesign.objects.filter(submitted_by=user, status='Pending').count()
        
        context['total_pending'] = context['pending_pre_count'] + context['pending_pr_count'] + context['pending_ad_count']

        # --- 3. Recent Activity (Combined) ---
        recent_activity = []
        
        # Fetch recent PRs
        prs = PurchaseRequest.objects.filter(submitted_by=user).order_by('-created_at')[:5]
        for pr in prs:
            recent_activity.append({
                'type': 'PR',
                'title': f"PR-{pr.pr_number}",
                'description': pr.purpose,
                'amount': pr.total_amount,
                'status': pr.status,
                'date': pr.created_at,
                'icon': '🛒'
            })
            
        # Fetch recent ADs
        ads = ActivityDesign.objects.filter(submitted_by=user).order_by('-created_at')[:5]
        for ad in ads:
            recent_activity.append({
                'type': 'AD',
                'title': ad.activity_title or f"AD-{ad.ad_number}",
                'description': ad.purpose,
                'amount': ad.total_amount,
                'status': ad.status,
                'date': ad.created_at,
                'icon': '🎯'
            })
            
        # Sort combined list by date descending
        recent_activity.sort(key=lambda x: x['date'], reverse=True)
        context['recent_activity'] = recent_activity[:5] # Limit to top 5 overall

        # --- 4. Quarterly Data (Actual Aggregation) ---
        from django.db.models.functions import Coalesce
        from apps.budgets.models import PRELineItem, PurchaseRequestAllocation, ActivityDesignAllocation
        from decimal import Decimal

        quarterly_data = []
        quarters = ['Q1', 'Q2', 'Q3', 'Q4']
        
        for q in quarters:
            # 1. Allocated (From PRE Line Items for this user's budget allocations)
            # Filter line items belonging to Approved PREs under the user's allocations
            # We explicitly check for 'Approved' PREs so we only count verified budgets
            allocated_q = PRELineItem.objects.filter(
                pre__budget_allocation__in=allocations,
                pre__status='Approved'
            ).aggregate(
                total=Coalesce(Sum(f'{q.lower()}_amount'), Decimal('0.00'))
            )['total']

            # 2. Consumed (From Approved PRs and ADs)
            
            # PR Consumption for this Quarter
            pr_consumed_q = PurchaseRequestAllocation.objects.filter(
                pre_line_item__pre__budget_allocation__in=allocations,
                quarter=q,
                purchase_request__status='Approved'
            ).aggregate(
                total=Coalesce(Sum('allocated_amount'), Decimal('0.00'))
            )['total']
            
            # AD Consumption for this Quarter
            ad_consumed_q = ActivityDesignAllocation.objects.filter(
                pre_line_item__pre__budget_allocation__in=allocations,
                quarter=q,
                activity_design__status='Approved'
            ).aggregate(
                total=Coalesce(Sum('allocated_amount'), Decimal('0.00'))
            )['total']
            
            consumed_q = pr_consumed_q + ad_consumed_q
            
            # 3. Utilization Calculation
            utilization_q = (consumed_q / allocated_q * 100) if allocated_q > 0 else 0
            
            quarterly_data.append({
                'quarter': q,
                'allocated': allocated_q,
                'consumed': consumed_q,
                'utilization': utilization_q
            })

        context['quarterly_data'] = quarterly_data

        return context


class DepartmentPREPageView(LoginRequiredMixin, TemplateView):
    template_name = 'end_user_panel/department_pre_page.html'  # Updated path
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        # 1. Get Budget Allocations for this user
        allocations = BudgetAllocation.objects.filter(
            end_user=user, 
            is_active=True
        ).select_related('approved_budget').annotate(
            has_submitted_pre=Exists(
                DepartmentPRE.objects.filter(
                    budget_allocation=OuterRef('pk')
                ).exclude(status='Rejected')
            ),
            has_draft_pre=Exists(
                PREDraft.objects.filter(
                    budget_allocation=OuterRef('pk')
                )
            )
        ).order_by('-allocated_at')
        
        context['budget_allocations'] = allocations
        context['has_budget'] = allocations.exists()
        # 2. Get Submitted PREs
        # PREs are linked to allocations, which are linked to the user.
        # OR if you have a direct 'submitted_by' field on DepartmentPRE:
        pres = DepartmentPRE.objects.filter(
            submitted_by=user
        ).order_by('-created_at')
        
        context['pres'] = pres
        
        # 3. Partially Approved Count (for the Alert)
        context['partially_approved_count'] = pres.filter(status='Partially Approved').count()
        return context
    
    
class UploadPREView(LoginRequiredMixin, View):
    template_name = 'end_user_panel/upload_pre.html'
    def get(self, request, allocation_id):
        allocation = get_object_or_404(BudgetAllocation, id=allocation_id, end_user=request.user)
        
        # Get or Create a PREDraft for this allocation
        draft, created = PREDraft.objects.get_or_create(
            budget_allocation=allocation,
            user=request.user,
            is_submitted=False
        )
        
        context = {
            'allocation': allocation,
            'draft': draft,
        }
        return render(request, self.template_name, context)
    def post(self, request, allocation_id):
        allocation = get_object_or_404(BudgetAllocation, id=allocation_id, end_user=request.user)
        draft = get_object_or_404(PREDraft, budget_allocation=allocation, user=request.user, is_submitted=False)
        
        action = request.POST.get('action')
        if action == 'upload_pre':
            if 'pre_document' in request.FILES:
                draft.uploaded_excel_file = request.FILES['pre_document']
                draft.pre_filename = request.FILES['pre_document'].name
                draft.save()
                messages.success(request, 'PRE Excel file uploaded successfully.')
            else:
                messages.error(request, 'No file selected.')
        elif action == 'upload_supporting':
            files = request.FILES.getlist('supporting_documents')
            if files:
                for f in files:
                    PREDraftSupportingDocument.objects.create(
                        draft=draft,
                        document=f,
                        file_name=f.name,
                        file_size=f.size
                    )
                messages.success(request, f'{len(files)} supporting document(s) uploaded.')
            else:
                messages.error(request, 'No supporting documents selected.')
        elif action == 'remove_supporting':
            doc_id = request.POST.get('doc_id')
            doc = get_object_or_404(PREDraftSupportingDocument, id=doc_id, draft=draft)
            doc.delete()
            messages.info(request, 'Document removed.')
        elif action == 'clear_draft':
            draft.delete() # Or clear fields if you prefer not to delete the object
            messages.warning(request, 'Draft cleared.')
            return redirect('department_pre_page')
        elif action == 'continue':
            if not draft.uploaded_excel_file or not draft.supporting_documents.exists():
                messages.error(request, 'Please upload all required files.')
            else:
                return redirect('preview_pre', pre_id=draft.id) # Next step URL
        return redirect('upload_pre', allocation_id=allocation_id)
    
class PreviewPREView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_staff == False or self.request.user.is_superuser == False
    def get_section_totals(self, items):
        """Helper to calculate totals for a list of items"""
        totals = {'q1': 0, 'q2': 0, 'q3': 0, 'q4': 0, 'total': 0}
        for item in items:
            totals['q1'] += item.get('q1', 0)
            totals['q2'] += item.get('q2', 0)
            totals['q3'] += item.get('q3', 0)
            totals['q4'] += item.get('q4', 0)
            totals['total'] += item.get('total', 0)
        return totals
    def get(self, request, pre_id): # Note: ID here refers to DRAFT ID from previous step
        try:
            draft = PREDraft.objects.get(id=pre_id, user=request.user)
        except PREDraft.DoesNotExist:
            messages.error(request, "Draft not found.")
            return redirect('department_pre_page')
        if not draft.uploaded_excel_file:
            messages.error(request, "No Excel file uploaded.")
            return redirect('upload_pre', draft.budget_allocation.id)
        # Run Parser
        try:
            with draft.uploaded_excel_file.open('rb') as f:
                result = parse_pre_excel_dynamic(f)
            
            if not result['success']:
                for error in result['errors']:
                    messages.error(request, error)
                return redirect('upload_pre', draft.budget_allocation.id)
            
            # Store extracted data in session for POST (submission)
            request.session['pre_preview_data'] = {
                'draft_id': str(draft.id),  # Convert UUID to string for JSON serialization
                'extracted_data': result['data'],
                'grand_total': result['grand_total'],
                'fiscal_year': result['fiscal_year']
            }
            context = {
                'draft': draft,
                'allocation': draft.budget_allocation,
                'extracted_data': result['data'],
                'grand_total': result['grand_total'],
                'fiscal_year': result['fiscal_year'],
                'validation_warnings': result['validation_summary'].get('row_total_mismatches', []),
                'receipts_total': self.get_section_totals(result['data']['receipts']),
                'personnel_total': self.get_section_totals(result['data']['personnel']),
                'mooe_total': self.get_section_totals(result['data']['mooe']),
                'capital_total': self.get_section_totals(result['data']['capital']),
            }
            return render(request, 'end_user_panel/preview_pre.html', context)
        except Exception as e:
            messages.error(request, f"Error parsing PRE file: {str(e)}")
            return redirect('upload_pre', draft.budget_allocation_id)
    def post(self, request, pre_id):
        action = request.POST.get('action')
        session_data = request.session.get('pre_preview_data')
        
        # Get draft first to access allocation_id for redirects
        draft = get_object_or_404(PREDraft, id=pre_id, user=request.user)
        
        if not session_data or str(session_data.get('draft_id')) != str(pre_id):
            messages.error(request, "Session expired. Please preview again.")
            return redirect('upload_pre', draft.budget_allocation.id)
        
        if action == 'cancel':
            # Optionally clear draft file here or just redirect
            return redirect('upload_pre', draft.budget_allocation.id)
        elif action == 'submit':
            try:
                with transaction.atomic():
                    # 1. Create DepartmentPRE
                    pre = DepartmentPRE.objects.create(
                        submitted_by=request.user,
                        department=draft.budget_allocation.department,
                        budget_allocation=draft.budget_allocation,
                        fiscal_year=session_data['fiscal_year'] or timezone.now().year,
                        total_amount=Decimal(str(session_data['grand_total'])),
                        status='Pending',
                        is_valid=True, # Validated by parser
                        submitted_at=timezone.now(),
                        uploaded_excel_file=draft.uploaded_excel_file # Move file reference
                    )
                    # NOTE: If you need to physically move file to new path, do it here. 
                    # Currently sharing the reference or relying on duplicate storage if configured.
                    # 2. Create Supporting Documents
                    for draft_doc in draft.supporting_documents.all():
                        DepartmentPRESupportingDocument.objects.create(
                            department_pre=pre,
                            document=draft_doc.document,
                            file_name=draft_doc.file_name,
                            file_size=draft_doc.file_size
                        )
                    # 3. Create Line Items
                    extracted_data = session_data['extracted_data']
                    self.create_line_items(pre, extracted_data)
                    # 4. Cleanup Draft
                    draft.delete()
                    
                    # Clear session
                    del request.session['pre_preview_data']
                    messages.success(request, f"PRE Submitted Successfully! Reference ID: {pre.id}")
                    return redirect('department_pre_page')
            except Exception as e:
                messages.error(request, f"Submission failed: {str(e)}")
                return redirect('preview_pre', pre_id)
        
        return redirect('preview_pre', pre_id)
    def create_line_items(self, pre, data):
        """Create PRELineItem records from parsed data"""
        category_map = {
            'receipts': 'RECEIPTS', 
            'personnel': 'PERSONNEL', 
            'mooe': 'MOOE', 
            'capital': 'CAPITAL'
        }
        
        for section, items in data.items():
            if not items: continue
            
            cat_type = category_map.get(section, 'MOOE')
            # Find or create category (Auto-create if missing to prevent data loss)
            category, _ = PRECategory.objects.get_or_create(
                category_type=cat_type,
                defaults={
                    'name': section.replace('_', ' ').title(), 
                    'sort_order': 0,
                    'code': cat_type  # Ensure unique code is provided
                }
            )
            
            for item in items:
                subcategory = None
                if item.get('subcategory') and item['subcategory'] != 'Uncategorized':
                    sub_name = item['subcategory']
                    # Fix UNIQUE constraint failed: budgets_presubcategory.category_id, budgets_presubcategory.code
                    subcategory, _ = PRESubCategory.objects.get_or_create(
                        category=category, 
                        name=sub_name,
                        defaults={
                            'code': slugify(sub_name).upper()[:50] or sub_name.upper().replace(' ', '_')[:50],
                            'sort_order': 0
                        }
                    )
                PRELineItem.objects.create(
                    pre=pre,
                    category=category,
                    subcategory=subcategory,
                    item_name=item['item_name'],
                    q1_amount=Decimal(str(item.get('q1', 0))),
                    q2_amount=Decimal(str(item.get('q2', 0))),
                    q3_amount=Decimal(str(item.get('q3', 0))),
                    q4_amount=Decimal(str(item.get('q4', 0)))
                )
                
                
class ViewPREDetailView(LoginRequiredMixin, View):
    def get(self, request, pre_id):
        # 1. Fetch the PRE object with optimized queries
        pre = get_object_or_404(
            DepartmentPRE.objects.select_related(
                'budget_allocation',
                'budget_allocation__approved_budget',
                'submitted_by'
            ).prefetch_related(
                'line_items__category',
                'line_items__subcategory',
                'supporting_documents',
                'signed_approved_documents', # Important for "Documents Submitted" section
            ),
            id=pre_id,
            # Ensure user can only see their own department's PREs (optional security)
            # submitted_by=request.user 
            # OR check budget_allocation.end_user == request.user
        )
        # 2. Calculate Totals by Category
        # Aggregate Q1-Q4 amounts for each category to show in summaries
        category_totals = pre.line_items.values(
            'category__name', 'category__category_type'
        ).annotate(
            total=Sum('q1_amount') + Sum('q2_amount') + Sum('q3_amount') + Sum('q4_amount')
        ).order_by('category__sort_order')
        # 3. Prepare Line Items with Budget Breakdown
        # This is CRITICAL for the "Budget Consumption Tracking" section.
        # It relies on the pre-existing logic in `PRELineItem.get_quarter_breakdown(quarter)`.
        line_items_with_breakdown = []
        
        # Determine if we should show breakdown (only if approved/active)
        if pre.status == 'Approved': 
             for item in pre.line_items.all():
                item_data = {
                    'item': item,
                    'quarters': []
                }
                for quarter in ['Q1', 'Q2', 'Q3', 'Q4']:
                    # Call the model method to get usage stats (Original, PR Consumed, AD Consumed, Available)
                    breakdown = item.get_quarter_breakdown(quarter)
                    item_data['quarters'].append(breakdown)
                
                line_items_with_breakdown.append(item_data)
        # 4. Filter Specific Document Types (Optional helpers for template)
        # You can also filter these in the template using the `document_type` field if available
        # or just pass `pre.signed_approved_documents.all()` as is.
        context = {
            'pre': pre,
            'category_totals': category_totals,
            'line_items_with_breakdown': line_items_with_breakdown, # Pass empty list if not approved
            'supporting_documents': pre.supporting_documents.all(),
        }
        return render(request, 'end_user_panel/view_pre_detail.html', context)
    
    
@login_required
@user_passes_test(lambda u: u.is_staff == False or u.is_superuser == False)
def upload_approved_pre_documents(request, pre_id):
    """
    Allow End User to upload signed documents for Partially Approved PREs.
    Updates status to 'Awaiting Admin Verification'.
    """
    pre = get_object_or_404(
        DepartmentPRE.objects.select_related('budget_allocation', 'submitted_by'),
        id=pre_id,
        submitted_by=request.user
    )
    # Security check: Only allow upload if status is correct
    if pre.status != 'Partially Approved':
        messages.error(request, 'Documents can only be uploaded for Partially Approved PREs.')
        return redirect('view_pre_detail', pre_id=pre.id)
    if request.method == 'POST':
        files = request.FILES.getlist('documents')
        document_types = request.POST.getlist('document_types')
        descriptions = request.POST.getlist('descriptions')
        if not files:
            messages.error(request, 'Please select at least one document to upload.')
            return redirect('view_pre_detail', pre_id=pre.id)
        # Validate file extensions
        allowed_extensions = ['pdf', 'jpg', 'jpeg', 'png']
        uploaded_count = 0
        for i, file in enumerate(files):
            file_ext = file.name.split('.')[-1].lower()
            if file_ext not in allowed_extensions:
                messages.warning(
                    request, 
                    f'File "{file.name}" skipped: Only PDF, JPG, and PNG files are allowed.'
                )
                continue
            # Fallback values
            doc_type = document_types[i] if i < len(document_types) else 'signed_pre'
            description = descriptions[i] if i < len(descriptions) else ''
            try:
                # Create the document record
                DepartmentPREApprovedDocument.objects.create(
                    pre=pre,
                    document=file,
                    file_name=file.name,
                    file_size=file.size,
                    document_type=doc_type,
                    uploaded_by=request.user,
                    description=description
                )
                uploaded_count += 1
            except Exception as e:
                messages.error(request, f'Error uploading "{file.name}": {str(e)}')
        if uploaded_count > 0:
            # Update PRE Status
            pre.status = 'Awaiting Admin Verification'
            pre.awaiting_verification = True
            pre.end_user_uploaded_at = timezone.now()
            pre.save()
            messages.success(
                request, 
                f'Successfully uploaded {uploaded_count} document(s). Your PRE is now awaiting admin verification.'
            )
        else:
            messages.error(request, 'No valid documents were uploaded.')
        return redirect('view_pre_detail', pre_id=pre.id)
    return redirect('view_pre_detail', pre_id=pre.id)


@login_required
@user_passes_test(lambda u: not u.is_staff and not u.is_superuser)
def budget_overview(request):
    """
    Main Budget Monitoring Dashboard - Overview Page
    Shows key metrics, charts, and recent activity
    """
    
    # 1. Get current year
    current_year = str(timezone.now().year)
    selected_year = request.GET.get('year', current_year)
    # 2. Fetch User's Budget Allocations for the year
    budget_allocations = BudgetAllocation.objects.filter(
        end_user=request.user,
        is_active=True,
        approved_budget__fiscal_year=selected_year
    ).select_related('approved_budget')
    # 3. Fetch Approved PREs (Source of Truth for "Total Allocated" if exists)
    approved_pres = DepartmentPRE.objects.filter(
        budget_allocation__in=budget_allocations,
        status__in=['Approved', 'Partially Approved']
    )
    # 4. Key Metrics Calculation
    
    # A. Total Amounts
    pre_grand_total = approved_pres.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    
    # B. Usage (Aggregated from BudgetAllocation fields if maintained)
    allocation_stats = budget_allocations.aggregate(
        pr_used=Sum('pr_amount_used'),
        ad_used=Sum('ad_amount_used'),
        allocated=Sum('allocated_amount')
    )
    
    total_pr_used = allocation_stats['pr_used'] or Decimal('0')
    total_ad_used = allocation_stats['ad_used'] or Decimal('0')
    total_used = total_pr_used + total_ad_used
    # C. Logic: Use PRE Total if approved, otherwise Budget Allocated
    if pre_grand_total > 0:
        total_allocated = pre_grand_total
        has_approved_pre = True
    else:
        total_allocated = allocation_stats['allocated'] or Decimal('0')
        has_approved_pre = False
    total_remaining = total_allocated - total_used
    
    utilization_percentage = 0
    if total_allocated > 0:
        utilization_percentage = (total_used / total_allocated) * 100
    # 5. Counts
    pre_count = approved_pres.count()
    
    pr_count = PurchaseRequest.objects.filter(
        budget_allocation__in=budget_allocations
    ).exclude(status__in=['Draft', 'Rejected', 'Cancelled']).count()
    ad_count = ActivityDesign.objects.filter(
        budget_allocation__in=budget_allocations
    ).exclude(status__in=['Draft', 'Rejected', 'Cancelled']).count()
    # 6. Quarterly Spending Trend (Calculated)
    from django.apps import apps
    
    # Get models dynamically
    PurchaseRequestAllocation = apps.get_model('budgets', 'PurchaseRequestAllocation')
    ActivityDesignAllocation = apps.get_model('budgets', 'ActivityDesignAllocation')
    
    quarterly_spending = {
        'Q1': Decimal('0'), 'Q2': Decimal('0'), 
        'Q3': Decimal('0'), 'Q4': Decimal('0')
    }
    
    # helper to process aggregations
    def get_quarter_sum(model_class, allocation_field):
        return model_class.objects.filter(
            # Filter by allocations linked to the user's active budgets
            **{f"{allocation_field}__budget_allocation__in": budget_allocations},
            # Only count APPROVED requests
            **{f"{allocation_field}__status": "Approved"}
        ).values('quarter').annotate(
            total=Sum('allocated_amount')
        ).order_by('quarter')
    # A. Calculate PR Spending per Quarter
    pr_spending = get_quarter_sum(PurchaseRequestAllocation, 'purchase_request')
    for item in pr_spending:
        q = item['quarter']
        if q in quarterly_spending:
            quarterly_spending[q] += item['total'] or Decimal('0')
    # B. Calculate AD Spending per Quarter
    ad_spending = get_quarter_sum(ActivityDesignAllocation, 'activity_design')
    for item in ad_spending:
        q = item['quarter']
        if q in quarterly_spending:
            quarterly_spending[q] += item['total'] or Decimal('0')
            
    # Result: quarterly_spending now contains real totals like {'Q1': 5000.00, 'Q2': 0, ...}
    
    # 7. Recent Activity (Consolidated)
    recent_activity = []
    # Get recent PREs
    recent_pres = DepartmentPRE.objects.filter(
        budget_allocation__in=budget_allocations
    ).exclude(status='Draft').order_by('-submitted_at')[:5]
    for item in recent_pres:
        recent_activity.append({
            'date': item.submitted_at or item.created_at,
            'type': 'PRE',
            'number': f"PRE-{item.id.hex[:8].upper()}",
            'purpose': f"{item.line_items.count()} Line Items",
            'amount': item.total_amount,
            'status': item.status
        })
    # Get recent PRs
    recent_prs = PurchaseRequest.objects.filter(
        budget_allocation__in=budget_allocations
    ).exclude(status='Draft').order_by('-created_at')[:5]
    for item in recent_prs:
        recent_activity.append({
            'date': item.created_at, # PRs might strictly use created_at until submitted
            'type': 'PR',
            'number': item.pr_number,
            'purpose': item.purpose,
            'amount': item.total_amount,
            'status': item.status
        })
        
    # Get recent ADs
    recent_ads = ActivityDesign.objects.filter(
        budget_allocation__in=budget_allocations
    ).exclude(status='Draft').order_by('-created_at')[:5]
    for item in recent_ads:
        recent_activity.append({
            'date': item.created_at,
            'type': 'AD',
            'number': item.ad_number if hasattr(item, 'ad_number') else f"AD-{item.id}",
            'purpose': item.purpose,
            'amount': item.total_amount,
            'status': item.status
        })
    # Sort consolidated list
    recent_activity.sort(key=lambda x: x['date'], reverse=True)
    recent_activity = recent_activity[:10]
    context = {
        'current_year': current_year,
        'total_allocated': total_allocated,
        'total_used': total_used,
        'total_remaining': total_remaining,
        'utilization_percentage': utilization_percentage,
        'has_approved_pre': has_approved_pre,
        'pre_grand_total': pre_grand_total,
        'total_pr_used': total_pr_used,
        'total_ad_used': total_ad_used,
        'pre_count': pre_count,
        'pr_count': pr_count,
        'ad_count': ad_count,
        'quarterly_spending': quarterly_spending,
        'recent_activity': recent_activity,
    }
    return render(request, 'end_user_panel/budget_overview.html', context)

@login_required
@user_passes_test(lambda u: not u.is_staff and not u.is_superuser)
def pre_budget_details(request):
    """
    PRE Budget Details Page
    Shows all PRE line items with quarterly breakdown
    """
    
    # 1. Get current year
    current_year = str(timezone.now().year)
    selected_year = request.GET.get('year', current_year)
    # 2. Base Query: User's Active Budget Allocations
    base_allocations = BudgetAllocation.objects.filter(
        end_user=request.user,
        is_active=True
    ).select_related('approved_budget')
    # 3. Get Available Years (Distinct Fiscal Years)
    available_years = (
        base_allocations
        .values_list('approved_budget__fiscal_year', flat=True)
        .distinct()
        .order_by('-approved_budget__fiscal_year')
    )
    # 4. Filter Allocations by Selected Year
    if selected_year and selected_year != 'all':
        budget_allocations = base_allocations.filter(
            approved_budget__fiscal_year=selected_year
        )
    else:
        budget_allocations = base_allocations
    # 5. Fetch Approved PREs
    # Only show Approved or Partially Approved PREs
    approved_pres = DepartmentPRE.objects.filter(
        budget_allocation__in=budget_allocations,
        status__in=['Approved', 'Partially Approved']
    ).prefetch_related(
        'line_items__category',
        'line_items__subcategory'
    ).order_by('-created_at')
    # 6. Build Data Structure for Template
    pre_data = []
    
    # We also need to track Totals by Category for the Pie Chart
    category_totals = {}
    for pre in approved_pres:
        line_items_data = []
        
        # Identify Total Consumed for the PRE
        # You might need to sum totals if your model doesn't store 'total_consumed'
        pre_total_consumed = Decimal('0')
        for line_item in pre.line_items.all():
            category_name = line_item.category.name if line_item.category else 'Other'
            
            # --- Quarter Logic ---
            quarters_data = {}
            item_total_budgeted = Decimal('0')
            item_total_consumed = Decimal('0')
            item_total_reserved = Decimal('0')
            item_total_available = Decimal('0')
            for quarter in ['Q1', 'Q2', 'Q3', 'Q4']:
                # Use model helper methods
                q_amount = line_item.get_quarter_amount(quarter)
                q_consumed = line_item.get_quarter_consumed(quarter)
                q_reserved = line_item.get_quarter_reserved(quarter)
                q_available = line_item.get_quarter_available(quarter)
                quarters_data[quarter] = {
                    'budgeted': q_amount,
                    'consumed': q_consumed,
                    'reserved': q_reserved,
                    'available': q_available
                }
                item_total_budgeted += q_amount
                item_total_consumed += q_consumed
                item_total_reserved += q_reserved
                item_total_available += q_available
            # Add to PRE total consumed
            pre_total_consumed += item_total_consumed
            # Add to Category Totals (for Chart)
            if category_name not in category_totals:
                category_totals[category_name] = Decimal('0')
            category_totals[category_name] += item_total_budgeted
            # Append structured data
            line_items_data.append({
                'item': line_item,
                'category': category_name,
                'quarters': quarters_data,
                'total_budgeted': item_total_budgeted,
                'total_consumed': item_total_consumed,
                'total_reserved': item_total_reserved,
                'total_available': item_total_available
            })
        pre_data.append({
            'pre': pre,
            'line_items': line_items_data,
            'total_amount': pre.total_amount,
            'total_consumed': pre_total_consumed,
            'total_remaining': pre.total_amount - pre_total_consumed
        })
    # 7. Context
    context = {
        'current_year': current_year,
        'selected_year': selected_year,
        'available_years': available_years,
        'pre_data': pre_data,
        'category_totals': category_totals,
    }
    return render(request, 'end_user_panel/pre_budget_details.html', context)


@login_required
@user_passes_test(lambda u: not u.is_staff and not u.is_superuser)
def quarterly_analysis(request):
    """
    Quarterly Budget Analysis Page
    Shows quarter-specific breakdown with tabs
    """
    
    # 1. Get current year and filters
    current_year = str(timezone.now().year)
    selected_year = request.GET.get('year', current_year)
    selected_quarter = request.GET.get('quarter', 'Q1')
    # 2. Base Query: User's Active Budget Allocations
    base_allocations = BudgetAllocation.objects.filter(
        end_user=request.user,
        is_active=True
    ).select_related('approved_budget')
    # 3. Get Available Years
    available_years = (
        base_allocations
        .values_list('approved_budget__fiscal_year', flat=True)
        .distinct()
        .order_by('-approved_budget__fiscal_year')
    )
    # 4. Filter Allocations by Selected Year
    if selected_year and selected_year != 'all':
        budget_allocations = base_allocations.filter(
            approved_budget__fiscal_year=selected_year
        )
    else:
        budget_allocations = base_allocations
    # 5. Get Approved PREs for Calculation
    approved_pres = DepartmentPRE.objects.filter(
        budget_allocation__in=budget_allocations,
        status__in=['Approved', 'Partially Approved']
    ).prefetch_related('line_items__category', 'line_items__subcategory')
    # 6. Calculate Quarter Summary
    quarter_total = Decimal('0')
    quarter_consumed = Decimal('0')
    quarter_reserved = Decimal('0')
    quarter_remaining = Decimal('0')
    # List for the table
    quarter_line_items = []
    for pre in approved_pres:
        for line_item in pre.line_items.all():
            # Use model helper method
            q_amount = line_item.get_quarter_amount(selected_quarter)
            if q_amount > 0:
                q_consumed = line_item.get_quarter_consumed(selected_quarter)
                q_reserved = line_item.get_quarter_reserved(selected_quarter)
                q_available = line_item.get_quarter_available(selected_quarter)
                category_name = line_item.category.name if line_item.category else 'Other'
                quarter_line_items.append({
                    'line_item': line_item,
                    'category': category_name,
                    'budgeted': q_amount,
                    'consumed': q_consumed,
                    'reserved': q_reserved,
                    'available': q_available
                })
                quarter_total += q_amount
                quarter_consumed += q_consumed
                quarter_reserved += q_reserved
                quarter_remaining += q_available
    # Calculate Utilization %
    quarter_utilization = 0
    if quarter_total > 0:
        quarter_utilization = ((quarter_consumed + quarter_reserved) / quarter_total) * 100
    # 7. Get Transaction History for this Quarter
    
    # PR Transactions
    # Note: Querying PurchaseRequestAllocation which has 'quarter' field
    pr_transactions = PurchaseRequestAllocation.objects.filter(
        purchase_request__budget_allocation__in=budget_allocations,
        quarter=selected_quarter
    ).exclude(
        purchase_request__status__in=['Draft', 'Rejected', 'Cancelled']
    ).select_related('purchase_request', 'pre_line_item').order_by('-purchase_request__submitted_at')
    # AD Transactions
    # Note: Querying ActivityDesignAllocation which has 'quarter' field
    ad_transactions = ActivityDesignAllocation.objects.filter(
        activity_design__budget_allocation__in=budget_allocations,
        quarter=selected_quarter
    ).exclude(
        activity_design__status__in=['Draft', 'Rejected', 'Cancelled']
    ).select_related('activity_design', 'pre_line_item').order_by('-activity_design__submitted_at')
    # Combine into unified list
    transactions = []
    
    for pr_alloc in pr_transactions:
        status = pr_alloc.purchase_request.status
        transactions.append({
            'date': pr_alloc.purchase_request.submitted_at or pr_alloc.allocated_at,
            'type': 'PR',
            'number': pr_alloc.purchase_request.pr_number,
            'line_item': pr_alloc.pre_line_item.item_name,
            'amount': pr_alloc.allocated_amount,
            'status': status
        })
    for ad_alloc in ad_transactions:
        status = ad_alloc.activity_design.status
        transactions.append({
            'date': ad_alloc.activity_design.submitted_at or ad_alloc.allocated_at,
            'type': 'AD',
            'number': ad_alloc.activity_design.ad_number if hasattr(ad_alloc.activity_design, 'ad_number') else 'AD',
            'line_item': ad_alloc.pre_line_item.item_name,
            'amount': ad_alloc.allocated_amount,
            'status': status
        })
    # Sort combined list by date descending
    transactions.sort(key=lambda x: x['date'] or timezone.now(), reverse=True)
    # 8. Context
    context = {
        'current_year': current_year,
        'selected_year': selected_year,
        'available_years': available_years,
        'selected_quarter': selected_quarter,
        'quarters': ['Q1', 'Q2', 'Q3', 'Q4'],
        # Summary
        'quarter_total': quarter_total,
        'quarter_consumed': quarter_consumed,
        'quarter_reserved': quarter_reserved,
        'quarter_remaining': quarter_remaining,
        'quarter_utilization': quarter_utilization,
        # Lists
        'quarter_line_items': quarter_line_items,
        'transactions': transactions,
    }
    return render(request, 'end_user_panel/quarterly_analysis.html', context)


@login_required
@user_passes_test(lambda u: not u.is_staff and not u.is_superuser)
def transaction_history(request):
    """
    Transaction History Page
    Shows all PREs, PRs, and ADs with filtering and pagination
    """
    
    # 1. Get filter parameters
    transaction_type = request.GET.get('type', 'all')
    status_filter = request.GET.get('status', 'all')
    quarter_filter = request.GET.get('quarter', 'all')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    # 2. Get user's active budget allocations
    budget_allocations = BudgetAllocation.objects.filter(
        end_user=request.user,
        is_active=True
    )
    transactions = []
    # 3. Get PRE Transactions
    if transaction_type in ['all', 'pre']:
        # Filter PREs
        pres = DepartmentPRE.objects.filter(
            budget_allocation__in=budget_allocations
        ).exclude(status='Draft')
        if status_filter != 'all':
            pres = pres.filter(status=status_filter)
        for pre in pres:
            # Determine quarters used by this PRE based on line items
            quarters_used = []
            for q in ['Q1', 'Q2', 'Q3', 'Q4']:
                # Helper: check manually if any line item has amount > 0 for this quarter
                # Uses the fields like q1_amount, q2_amount...
                if pre.line_items.filter(**{f'{q.lower()}_amount__gt': 0}).exists():
                    quarters_used.append(q)
            # Apply quarter filter for PRE
            if quarter_filter != 'all' and quarter_filter not in quarters_used:
                continue
            transactions.append({
                'date': pre.submitted_at or pre.created_at,
                'type': 'PRE',
                'number': f"{pre.department} - FY {pre.fiscal_year}",
                'line_item': f"{pre.line_items.count()} Line Items",
                'quarter': ', '.join(quarters_used) if quarters_used else 'All',
                'amount': pre.total_amount,
                'status': pre.status
            })
    # 4. Get Purchase Request (PR) Transactions
    if transaction_type in ['all', 'pr']:
        prs = PurchaseRequest.objects.filter(
            budget_allocation__in=budget_allocations
        ).exclude(status='Draft').prefetch_related('pre_allocations__pre_line_item')
        if status_filter != 'all':
            prs = prs.filter(status=status_filter)
        for pr in prs:
            allocations = pr.pre_allocations.all()
            if allocations:
                # Group by quarter and line item names
                quarters = set(alloc.quarter for alloc in allocations)
                line_items = set(alloc.pre_line_item.item_name for alloc in allocations)
                # Apply quarter filter
                if quarter_filter != 'all' and quarter_filter not in quarters:
                    continue
                line_item_str = ', '.join(list(line_items)[:2])
                if len(line_items) > 2:
                    line_item_str += '...'
                transactions.append({
                    'date': pr.submitted_at or pr.created_at,
                    'type': 'PR',
                    'number': pr.pr_number,
                    'line_item': line_item_str,
                    'quarter': ', '.join(sorted(quarters)),
                    'amount': pr.total_amount,
                    'status': pr.status
                })
    # 5. Get Activity Design (AD) Transactions
    if transaction_type in ['all', 'ad']:
        ads = ActivityDesign.objects.filter(
            budget_allocation__in=budget_allocations
        ).exclude(status='Draft').prefetch_related('pre_allocations__pre_line_item')
        if status_filter != 'all':
            ads = ads.filter(status=status_filter)
        for ad in ads:
            allocations = ad.pre_allocations.all()
            if allocations:
                quarters = set(alloc.quarter for alloc in allocations)
                line_items = set(alloc.pre_line_item.item_name for alloc in allocations)
                # Apply quarter filter
                if quarter_filter != 'all' and quarter_filter not in quarters:
                    continue
                line_item_str = ', '.join(list(line_items)[:2])
                if len(line_items) > 2:
                    line_item_str += '...'
                transactions.append({
                    'date': ad.submitted_at or ad.created_at,
                    'type': 'AD',
                    'number': ad.ad_number if hasattr(ad, 'ad_number') else 'AD',
                    'line_item': line_item_str,
                    'quarter': ', '.join(sorted(quarters)),
                    'amount': ad.total_amount,
                    'status': ad.status
                })
    # 6. Apply Date Filters (In Memory)
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            transactions = [t for t in transactions if t['date'] and t['date'].date() >= date_from_obj]
        except ValueError:
            pass
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            transactions = [t for t in transactions if t['date'] and t['date'].date() <= date_to_obj]
        except ValueError:
            pass
    # 7. Sort by Date Descending
    transactions.sort(key=lambda x: x['date'] if x['date'] else timezone.now(), reverse=True)
    # 8. Pagination
    paginator = Paginator(transactions, 20)  # Show 20 per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    # 9. Context
    context = {
        'transactions': page_obj,
        'transaction_type': transaction_type,
        'status_filter': status_filter,
        'quarter_filter': quarter_filter,
        'date_from': date_from,
        'date_to': date_to,
        'total_count': len(transactions),
    }
    return render(request, 'end_user_panel/transaction_history.html', context)


@login_required
@user_passes_test(lambda u: not u.is_staff and not u.is_superuser)
def budget_reports(request):
    """
    Reports & Export Hub Page
    Provides access to different report types:
    - Budget Summary
    - Quarterly Report
    - Category-wise Report
    - Transaction Report
    """
    
    # Context data for dropdowns
    context = {
        'quarters': ['Q1', 'Q2', 'Q3', 'Q4'],
        # You can add more dynamic context here later if needed
    }
    return render(request, 'end_user_panel/budget_reports.html', context)


@login_required
@user_passes_test(lambda u: not u.is_staff and not u.is_superuser)
def pr_ad_list(request):
    """
    Purchase Requests & Activity Designs List Page
    Lists all PRs and ADs submitted by the user's department(s)
    """
    
    # 1. Get user's active budget allocations to identify relevant departments/scopes
    budget_allocations = BudgetAllocation.objects.filter(
        end_user=request.user,
        is_active=True
    )
    # 2. Fetch Purchase Requests (PRs)
    # Filter PRs linked to user's allocations or submitted by user (adjust logic based on precise requirements)
    purchase_requests = PurchaseRequest.objects.filter(
        budget_allocation__in=budget_allocations
    ).order_by('-created_at')
    # 3. Fetch Activity Designs (ADs)
    activity_designs = ActivityDesign.objects.filter(
        budget_allocation__in=budget_allocations
    ).order_by('-created_at')
    # 4. Calculate Summary Statistics
    pr_pending_count = purchase_requests.filter(status='Pending').count()
    pr_approved_count = purchase_requests.filter(status='Approved').count()
    
    ad_pending_count = activity_designs.filter(status='Pending').count()
    ad_approved_count = activity_designs.filter(status='Approved').count()
    # 5. Context
    context = {
        'purchase_requests': purchase_requests,
        'activity_designs': activity_designs,
        'pr_pending_count': pr_pending_count,
        'pr_approved_count': pr_approved_count,
        'ad_pending_count': ad_pending_count,
        'ad_approved_count': ad_approved_count,
    }
    return render(request, 'end_user_panel/purchase_request_list.html', context)

@login_required
def purchase_request_upload(request):
    """
    Handle PR document upload using PRDraft intermediate storage.
    """
    # 1. Get or Create Draft
    draft, created = PRDraft.objects.get_or_create(user=request.user)
    
    # 2. Context Data
    current_fiscal_year = str(datetime.now().year)
    budget_allocations = BudgetAllocation.objects.filter(
        department=request.user.department,
        is_active=True,
        approved_budget__fiscal_year=current_fiscal_year
    ).select_related('approved_budget')
    auto_selected_allocation = budget_allocations.first() if budget_allocations.count() == 1 else None
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # === ACTION: UPLOAD PR DOCUMENT ===
        if action == 'upload_pr':
            form = PurchaseRequestUploadForm(request.POST, request.FILES)
            if form.is_valid():
                # Delete old if exists
                if draft.pr_file:
                    draft.pr_file.delete(save=False)
                
                f = form.cleaned_data['pr_document']
                draft.pr_file = f
                draft.pr_filename = f.name
                draft.save()
                messages.success(request, "PR Document uploaded successfully.")
            else:
                 messages.error(request, f"Upload failed: {form.errors}")
            return redirect('purchase_request_upload')
        # === ACTION: UPLOAD SUPPORTING DOCS ===
        elif action == 'upload_supporting':
            form = PurchaseRequestSupportingDocForm(request.POST, request.FILES)
            files = request.FILES.getlist('supporting_documents')
            if files:
                for f in files:
                    PRDraftSupportingDocument.objects.create(
                        draft=draft,
                        document=f,
                        file_name=f.name,
                        file_size=f.size
                    )
                messages.success(request, f"{len(files)} supporting documents uploaded.")
            else:
                messages.error(request, "No files selected.")
            return redirect('purchase_request_upload')
        # === ACTION: REMOVE FILE ===
        elif action == 'remove_pr':
            if draft.pr_file:
                draft.pr_file.delete()
                draft.pr_filename = ''
                draft.save()
            return redirect('purchase_request_upload')
            
        elif 'remove_doc_id' in request.POST:
            doc_id = request.POST.get('remove_doc_id')
            doc = get_object_or_404(PRDraftSupportingDocument, id=doc_id, draft=draft)
            doc.delete()
            return redirect('purchase_request_upload')
        # === ACTION: FINAL SUBMIT ===
        elif action == 'submit_final':
            if not draft.pr_file:
                messages.error(request, "Please upload a PR Document first.")
                return redirect('purchase_request_upload')
                
            form = PurchaseRequestDetailsForm(request.POST)
            if form.is_valid():
                data = form.cleaned_data
                try:
                    with transaction.atomic():
                        # Parse Source
                        pre_id, line_item_id, quarter = data['source_of_fund'].split('|')
                        
                        budget_allocation = BudgetAllocation.objects.get(id=data['budget_allocation'])
                        pre_line_item = PRELineItem.objects.get(id=line_item_id)
                        
                        # Create Real PR
                        pr = PurchaseRequest.objects.create(
                            submitted_by=request.user,
                            department=request.user.department,
                            budget_allocation=budget_allocation,
                            pr_number=f"PR-{datetime.now().strftime('%Y%m%d')}-{PurchaseRequest.objects.count()+1:04d}",
                            purpose=data['purpose'],
                            total_amount=data['total_amount'],
                            status='Pending',
                            # Transfer file from Draft to PR
                            # Note: Cloudinary/Django file assignment typically handles the copy or reference
                            uploaded_document=draft.pr_file
                        )
                        
                        # Create Allocation
                        PurchaseRequestAllocation.objects.create(
                            purchase_request=pr,
                            pre_line_item=pre_line_item,
                            quarter=quarter,
                            allocated_amount=data['total_amount']
                        )
                        
                        # Transfer Supporting Docs
                        for draft_doc in draft.supporting_documents.all():
                            PurchaseRequestSupportingDocument.objects.create(
                                purchase_request=pr,
                                document=draft_doc.document,
                                file_name=draft_doc.file_name,
                                file_size=draft_doc.file_size
                            )
                        
                        # Clear Draft
                        draft.delete()
                        
                        messages.success(request, "Purchase Request submitted successfully!")
                        return redirect('pr_ad_list')
                except Exception as e:
                    messages.error(request, f"Error creating PR: {str(e)}")
            else:
                 messages.error(request, f"Form errors: {form.errors}")
    
    context = {
        'draft': draft,
        'budget_allocations': budget_allocations,
        'auto_selected_allocation': auto_selected_allocation,
        'current_fiscal_year': current_fiscal_year,
    }
    return render(request, 'end_user_panel/purchase_request_upload_form.html', context)
@login_required
def get_pre_line_items(request):
    """
    AJAX endpoint to get available PRE line items for a budget allocation.
    Returns line items that have remaining balance for the current/future quarters.
    """
    allocation_id = request.GET.get('allocation_id')
    
    if not allocation_id:
        return JsonResponse({'success': False, 'error': 'Missing allocation ID'})
        
    try:
        allocation = BudgetAllocation.objects.get(id=allocation_id)
        
        # Get all approved PREs for this allocation
        pres = DepartmentPRE.objects.filter(
            budget_allocation=allocation,
            status='Approved'
        ).prefetch_related('line_items')
        
        line_items_data = []
        
        for pre in pres:
            for item in pre.line_items.all():
                # We need to send back available options.
                # Logic: Check availability for each quarter (Q1, Q2, Q3, Q4)
                
                quarters = ['Q1', 'Q2', 'Q3', 'Q4']
                
                for q in quarters:
                    # Use the helper method from the model
                    available = item.get_quarter_available(q) or 0
                    if available > 0:
                        line_items_data.append({
                            'value': f"{pre.id}|{item.id}|{q}", # encoded ID for submission
                            'display': f"{item.item_name}", # Assumes item.line_item.name exists, verify if needed
                            'quarter': q,
                            'available': float(available)
                        })
                        
        return JsonResponse({'success': True, 'line_items': line_items_data})
        
    except BudgetAllocation.DoesNotExist:
         return JsonResponse({'success': False, 'error': 'Allocation not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    
    
class ViewPRDetailView(LoginRequiredMixin, DetailView):
    model = PurchaseRequest
    template_name = 'end_user_panel/view_pr_detail.html'
    context_object_name = 'pr'
    pk_url_kwarg = 'pr_id'
    def get_queryset(self):
        # Security: Users can only view their own PRs
        return PurchaseRequest.objects.filter(submitted_by=self.request.user)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pr = self.object
        
        # 1. Get the Primary Allocation (The specific PRE Line Item used)
        # We assume 1 PR maps to 1 Allocation for this version
        # You might need to adjust the related name 'pre_allocations' based on your exact model definition
        # If PurchaseRequestAllocation model exists:
        allocation = pr.pre_allocations.select_related(
            'pre_line_item__category',
            'pre_line_item__pre' 
        ).first()
        
        context['allocation'] = allocation
        
        # 2. Budget Breakdown Calculation
        # We need to show: Total Budget, Total Used (All PRs/ADs), Remaining
        if pr.budget_allocation:
            budget_alloc = pr.budget_allocation
            
            # Calculate Total Consumed by *ALL* PRs for this budget allocation
            total_pr_consumed = budget_alloc.purchase_requests.exclude(
                status__in=['Rejected', 'Draft']
            ).aggregate(total=Coalesce(Sum('total_amount'), Decimal('0.00')))['total']
            
            # Calculate Total Consumed by *ALL* Activity Designs (if linked to same budget)
            # Assuming ActivityDesign model exists and links to BudgetAllocation
            # total_ad_consumed = budget_alloc.activity_designs.exclude(...).aggregate(...)
            total_ad_consumed = Decimal('0.00') # Placeholder until AD is fully integrated
            total_used = total_pr_consumed + total_ad_consumed
            remaining = budget_alloc.allocated_amount - total_used
            context['budget_summary'] = {
                'allocated': budget_alloc.allocated_amount,
                'total_used': total_used,
                'remaining': remaining,
                'pr_used': total_pr_consumed,
                'ad_used': total_ad_consumed
            }
        # 3. Quarter-Specific Details (If allocation exists)
        if allocation:
            line_item = allocation.pre_line_item
            quarter = allocation.quarter # e.g., 'Q1'
            
            # A. Get Original Budget for this specific Quarter
            # PRELineItem has fields q1_amount, q2_amount...
            quarter_field = f"{quarter.lower()}_amount"
            original_amount = getattr(line_item, quarter_field, Decimal('0.00'))
            
            # B. Calculate "Consumed Before" (By OTHER PRs/ADs for this Item + Quarter)
            # We filter for allocations linked to this Line Item + Quarter
            # And exclude the current PR to see what was used *before* this request
            from apps.budgets.models import PurchaseRequestAllocation
            
            consumed_others = PurchaseRequestAllocation.objects.filter(
                pre_line_item=line_item,
                quarter=quarter,
                purchase_request__status__in=['Pending', 'Partially Approved', 'Awaiting Admin Verification', 'Approved']
            ).exclude(
                purchase_request=pr # Exclude this PR
            ).aggregate(
                total=Coalesce(Sum('allocated_amount'), Decimal('0.00'))
            )['total']
            
            # Placeholder for AD consumption (Add this when AD model is ready)
            # ad_consumed = ActivityDesignAllocation.objects.filter(...).aggregate(...)
            ad_consumed = Decimal('0.00') 
            
            consumed_total_others = consumed_others + ad_consumed
            
            # C. This PR's Usage
            this_pr_usage = allocation.allocated_amount
            
            # D. Remaining
            remaining = original_amount - consumed_total_others - this_pr_usage
            
            context['quarter_details'] = {
                'quarter': quarter,
                'original': original_amount,
                'consumed_before': consumed_total_others,
                'this_pr': this_pr_usage,
                'remaining': remaining
            }
        return context
    
    
@login_required
@require_POST
def upload_signed_pr_docs(request, pr_id):
    pr = get_object_or_404(PurchaseRequest, id=pr_id, submitted_by=request.user)
    
    # Validation: Only allow upload if Partially Approved
    if pr.status != 'Partially Approved':
        messages.error(request, "You can only upload signed documents when status is 'Partially Approved'.")
        return redirect('view_pr_detail', pr_id=pr.id)
        
    uploaded_files = request.FILES.getlist('signed_documents')
    
    if not uploaded_files:
        messages.error(request, "Please select at least one file.")
        return redirect('view_pr_detail', pr_id=pr.id)
    try:
        # Save each file
        # Note: You might want a specific model field or a 'type' field to distinguish these
        # If reusing PurchaseRequestSupportingDocument, maybe add a description prefix
        
        # Checking if you have a specific 'SignedDocument' model or related name 'signed_approved_documents'
        # based on the template {{ pre.signed_approved_documents.all }}
        # If 'signed_approved_documents' is a related_name on PurchaseRequestApprovedDocument model:
        
        from apps.budgets.models import PurchaseRequestApprovedDocument # Import if exists
        
        for f in uploaded_files:
            PurchaseRequestApprovedDocument.objects.create(
                purchase_request=pr,
                document=f,
                file_name=f.name,
                uploaded_by=request.user,
                document_type='signed_pr'
            )
            
        # Update PR Status
        pr.status = 'Awaiting Admin Verification'
        pr.save() # Ensure 'end_user_uploaded_at' auto-updates or set it manually
        
        messages.success(request, "Signed documents uploaded successfully! Admin will verify them shortly.")
        
    except Exception as e:
        messages.error(request, f"Error uploading files: {str(e)}")
        
    return redirect('view_pr_detail', pr_id=pr.id)


@login_required
def activity_design_upload(request):
    current_year = str(timezone.now().year)
    active_allocation = BudgetAllocation.objects.filter(
        end_user=request.user, 
        is_active=True,
        approved_budget__fiscal_year=current_year
    ).first()
    # Draft Logic (Session based like PR)
    draft_id = request.session.get('ad_draft_id')
    draft = None
    if draft_id:
        draft = ActivityDesign.objects.filter(id=draft_id, status='Draft').first()
    # Pre-populate Final Request Form if draft exists
    if draft:
        form = ActivityDesignDetailsForm(instance=draft)
    else:
        form = ActivityDesignDetailsForm()
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # --- ACTION: UPLOAD AD (AJAX) ---
        if action == 'upload_ad':
            upload_form = ActivityDesignUploadForm(request.POST, request.FILES)
            if upload_form.is_valid():
                f = upload_form.cleaned_data['ad_document']
                if not draft:
                    draft = ActivityDesign.objects.create(
                        submitted_by=request.user,
                        budget_allocation=active_allocation, # Temporary bind
                        status='Draft',
                        ad_number=f"DRAFT-{uuid.uuid4().hex[:6].upper()}",
                        total_amount=0
                    )
                    request.session['ad_draft_id'] = str(draft.id)
                
                draft.uploaded_document = f
                draft.save()
                return JsonResponse({'success': True, 'message': 'AD Document uploaded'})
            else:
                return JsonResponse({'success': False, 'error': upload_form.errors.as_text()})
        # --- ACTION: UPLOAD SUPPORTING (AJAX) ---
        elif action == 'upload_supporting':
            # Note: We manually handle list of files because Form.cleaned_data only returns one if not handled carefully
            # But relying on request.FILES.getlist is safer for multi-upload
            if not draft:
                 draft = ActivityDesign.objects.create(
                    submitted_by=request.user,
                    budget_allocation=active_allocation,
                    status='Draft',
                    ad_number=f"DRAFT-{uuid.uuid4().hex[:6].upper()}",
                    total_amount=0
                )
                 request.session['ad_draft_id'] = str(draft.id)
            files = request.FILES.getlist('supporting_documents')
            if not files:
                 return JsonResponse({'success': False, 'error': 'No files selected'})
            for f in files:
                ActivityDesignSupportingDocument.objects.create(
                    activity_design=draft,
                    document=f,
                    file_name=f.name,
                    file_size=f.size,
                    uploaded_by=request.user
                )
            return JsonResponse({'success': True, 'message': f'{len(files)} files uploaded'})
        # --- ACTION: REMOVE AD ---
        elif action == 'remove_ad':
            if draft and draft.uploaded_document:
                draft.uploaded_document.delete() 
                draft.uploaded_document = None
                draft.save()
            return JsonResponse({'success': True, 'message': 'File removed'})
        # --- ACTION: REMOVE SUPPORTING ---
        elif action == 'remove_supporting':
            doc_id = request.POST.get('doc_id')
            ActivityDesignSupportingDocument.objects.filter(id=doc_id, activity_design=draft).delete()
            return JsonResponse({'success': True, 'message': 'File removed'})
        
        # --- ACTION: ADD DRAFT ALLOCATION (SESSION ONLY) ---
        elif action == 'add_draft_allocation':
            try:
                allocations = request.session.get('ad_draft_allocations', [])
                new_item = {
                    'line_item_id': request.POST.get('line_item_id'),
                    'quarter': request.POST.get('quarter'),
                    'amount': float(request.POST.get('amount')),
                    'text': request.POST.get('text'),
                    'full_value': request.POST.get('full_value') # For filtering
                }
                allocations.append(new_item)
                request.session['ad_draft_allocations'] = allocations
                request.session.modified = True
                
                # Calculate total
                total = sum(d['amount'] for d in allocations)
                return JsonResponse({
                    'success': True, 
                    'allocations': allocations,
                    'total': total
                })
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)})

        # --- ACTION: REMOVE DRAFT ALLOCATION (SESSION ONLY) ---
        elif action == 'remove_draft_allocation':
            try:
                index = int(request.POST.get('index'))
                allocations = request.session.get('ad_draft_allocations', [])
                if 0 <= index < len(allocations):
                    allocations.pop(index)
                    request.session['ad_draft_allocations'] = allocations
                    request.session.modified = True
                
                total = sum(d['amount'] for d in allocations)
                return JsonResponse({
                    'success': True, 
                    'allocations': allocations,
                    'total': total
                })
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)})
        # --- ACTION: SUBMIT FINAL ---
        elif action == 'submit_final':
            # Handle case where no draft logic existed yet
            if not draft:
                draft = ActivityDesign(
                    submitted_by=request.user,
                    status='Draft',
                    ad_number=f"DRAFT-{uuid.uuid4().hex[:6].upper()}"
                )
            
            # Use Details Form
            details_form = ActivityDesignDetailsForm(request.POST, instance=draft)
            
            if details_form.is_valid():
                with transaction.atomic():
                    ad = details_form.save(commit=False)
                    ad.status = 'Pending'
                    # Ensure total_amount is not None for DB constraint (re-calculated below)
                    if ad.total_amount is None:
                        ad.total_amount = Decimal('0.00')
                    
                    # Ensure real AD Number
                    if not ad.ad_number.startswith('AD-'):
                         ad.ad_number = f"AD-{uuid.uuid4().hex[:8].upper()}"
                    
                    # Link Budget Allocation
                    alloc_id = details_form.cleaned_data['budget_allocation']
                    ad.budget_allocation_id = alloc_id
                    
                    # Handle main file if uploaded during final submit (fallback)
                    if 'ad_document' in request.FILES:
                         ad.uploaded_document = request.FILES['ad_document']
                    
                    ad.save()
                    
                    # Process Allocations JSON
                    line_items_json = details_form.cleaned_data['line_items_data']
                    items_data = json.loads(line_items_json)
                    total_allocated = Decimal('0')
                    
                    # Clear old allocations to prevent duplicates
                    ad.pre_allocations.all().delete()
                    
                    for item in items_data:
                        line_item = PRELineItem.objects.get(id=item['line_item_id'])
                        amount = Decimal(str(item['amount']))
                        ActivityDesignAllocation.objects.create(
                            activity_design=ad,
                            pre_line_item=line_item,
                            quarter=item['quarter'],
                            allocated_amount=amount
                        )
                        total_allocated += amount
                    
                    # 3. Update Total Amount final check
                    ad.total_amount = total_allocated
                    ad.save()
                    
                    # Clear session
                    if 'ad_draft_id' in request.session:
                        del request.session['ad_draft_id']
                    if 'ad_draft_allocations' in request.session:
                        del request.session['ad_draft_allocations']
                        
                    messages.success(request, "Activity Design submitted successfully!")
                    return redirect('pr_ad_list') 
            else:
                messages.error(request, f"Form Errors: {details_form.errors}")
    
    context = {
        'form': form,
        'draft': draft,
        'active_allocation': active_allocation,
        'draft_allocations': json.dumps(request.session.get('ad_draft_allocations', [])), # Pass as JSON for JS
    }
    return render(request, 'end_user_panel/activity_design_upload.html', context)


class ActivityDesignDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """
    View to display details of a specific Activity Design.
    Shows status, uploaded documents, and multi-source funding allocations.
    """
    model = ActivityDesign
    template_name = 'end_user_panel/view_ad_detail.html'
    context_object_name = 'ad'
    pk_url_kwarg = 'ad_id' # We will use 'ad_id' in the URL
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ad = self.object
        
        # 1. Get all funding allocations for this AD
        # rel 'pre_allocations' fetches related ActivityDesignAllocation objects
        context['allocations'] = ad.pre_allocations.select_related(
            'pre_line_item', 
            'pre_line_item__category'
        ).all()
        
        # 2. Add Budget Summary of the Parent Allocation (Optional but helpful)
        # This shows the user how much is left in the main pot
        if ad.budget_allocation:
            allocation = ad.budget_allocation
            context['budget_summary'] = {
                'title': allocation.approved_budget.title,
                'total_budget': allocation.allocated_amount,
                'total_used': allocation.pr_amount_used + allocation.ad_amount_used,
                # Simple calculation for context display
                'remaining': allocation.allocated_amount - (allocation.pr_amount_used + allocation.ad_amount_used)
            }
        
        return context
    def test_func(self):
        """
        Security Check:
        Only allow access if the user is:
        1. Wait, Staff/Admins usually have their own panel, but if they use this view: ALLOW.
        2. The Creator of the AD (submitted_by == user).
        """
        ad = self.get_object()
        
        # Allow ifsuperuser or staff
        if self.request.user.is_superuser or self.request.user.is_staff:
            return True
            
        # Allow if owner
        return ad.submitted_by == self.request.user


@login_required
@require_POST
def upload_signed_ad_docs(request, ad_id):
    """
    Handle the upload of signed Activity Design documents.
    Updates status from 'Partially Approved' -> 'Awaiting Admin Verification'.
    """
    # 1. Fetch AD and verify ownership
    ad = get_object_or_404(ActivityDesign, id=ad_id, submitted_by=request.user)
    
    # 2. Status Validation
    if ad.status != 'Partially Approved':
        messages.error(request, "You can only upload signed documents when status is 'Partially Approved'.")
        return redirect('view_ad_detail', ad_id=ad.id)
        
    uploaded_files = request.FILES.getlist('signed_documents')
    
    if not uploaded_files:
        messages.error(request, "Please select at least one file.")
        return redirect('view_ad_detail', ad_id=ad.id)

    try:
        from apps.budgets.models import ActivityDesignApprovedDocument

        # 3. Save each file
        for f in uploaded_files:
            ActivityDesignApprovedDocument.objects.create(
                activity_design=ad,
                document=f,
                file_name=f.name,
                uploaded_by=request.user,
                document_type='signed_ad',  # Default type
                file_size=f.size
            )
            
        # 4. Update AD Status & Timestamps
        ad.status = 'Awaiting Admin Verification'
        ad.end_user_uploaded_at = timezone.now()
        ad.awaiting_verification = True
        ad.save() 
        
        messages.success(request, "Signed documents uploaded successfully! Admin will verify them shortly.")
        
    except Exception as e:
        messages.error(request, f"Error uploading files: {str(e)}")
        
    return redirect('view_ad_detail', ad_id=ad.id)


class PREBudgetRealignmentView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    template_name = 'end_user_panel/pre_budget_realignment.html'
    form_class = PREBudgetRealignmentForm
    success_url = '/end_user/department-pre/' # Redirect to PRE Dashboard

    def test_func(self):
        return not self.request.user.is_staff and not self.request.user.is_superuser

    def get_initial(self):
        # We don't need initial data for empty form, dynamic data is loaded in form_kwargs or frontend
        return super().get_initial()

    def get_available_lines(self):
        """Helper to get available source line items"""
        approved_pres = DepartmentPRE.objects.filter(
            submitted_by=self.request.user,
            status='Approved'  # Only fully approved PREs
        )
        
        choices = []
        for pre in approved_pres:
            for item in pre.line_items.all():
                # Get remaining budgets using the same logic as API
                # But here we just need keys for the dropdown, maybe some label info
                # Real checking happens in Javascript API or cleaning
                
                # Simplified label: "Category - Item Name"
                label = f"{item.category.name} - {item.item_name}"
                
                # Check actual availability (sum of Q1-Q4 remaining)
                total_remaining = Decimal('0')
                for q in ['Q1', 'Q2', 'Q3', 'Q4']:
                    allocated = item.get_quarter_amount(q)
                    consumed = item.get_quarter_consumed(q) # PR/AD Approved
                    reserved = item.get_quarter_reserved(q) # Pending PR/AD
                    
                    # Also check Pending Realignments (Source)
                    pending_realign = PREBudgetRealignment.objects.filter(
                        source_item_key=str(item.id),
                        source_pre=pre,
                        status__in=['Pending', 'Partially Approved', 'Awaiting Admin Verification']
                    ).aggregate(
                        total=Coalesce(Sum(f'{q.lower()}_amount'), Decimal('0'))
                    )['total']
                    
                    remaining = allocated - consumed - reserved - pending_realign
                    if remaining > 0:
                        total_remaining += remaining

                if total_remaining > 0:
                    # Value format: pre_id|item_id
                    value = f"{pre.id}|{item.id}"
                    choices.append((value, f"{label} (₱{total_remaining:,.2f} Avail)"))
        
        return choices

    def get_target_lines(self):
        """Helper to get all possible target line items"""
        approved_pres = DepartmentPRE.objects.filter(
            submitted_by=self.request.user,
            status='Approved'
        )
        choices = []
        for pre in approved_pres:
            for item in pre.line_items.all():
                label = f"{item.category.name} - {item.item_name}"
                value = f"{pre.id}|{item.id}"
                choices.append((value, label))
        return choices

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['source_choices'] = self.get_available_lines()
        kwargs['target_choices'] = self.get_target_lines()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Check if user has any approved PREs
        context['approved_pres_count'] = DepartmentPRE.objects.filter(
            submitted_by=self.request.user, 
            status='Approved'
        ).count()
        return context

    def form_valid(self, form):
        data = form.cleaned_data
        user = self.request.user
        
        # Parse Source and Target
        source_pre_id, source_item_id = data['source_category'].split('|')
        target_pre_id, target_item_id = data['target_category'].split('|')
        
        try:
            source_pre = DepartmentPRE.objects.get(id=source_pre_id, submitted_by=user)
            target_pre = DepartmentPRE.objects.get(id=target_pre_id, submitted_by=user)
            
            # Create Realignment Record
            realignment = PREBudgetRealignment.objects.create(
                requested_by=user,
                source_pre=source_pre,
                source_item_key=source_item_id,
                target_pre=target_pre,
                target_item_key=target_item_id,
                reason=data['reason'],
                q1_amount=data['q1_amount'] or 0,
                q2_amount=data['q2_amount'] or 0,
                q3_amount=data['q3_amount'] or 0,
                q4_amount=data['q4_amount'] or 0,
                status='Pending',
                # Populate display names for easier history viewing
                source_item_display=dict(form.fields['source_category'].choices).get(data['source_category']),
                target_item_display=dict(form.fields['target_category'].choices).get(data['target_category']),
                updated_at=timezone.now()
            )
            
            # Handle File Uploads (Supports Multiple)
            files = self.request.FILES.getlist('documents')
            
            for f in files:
                # Convert Image to PDF if needed
                file_name = f.name
                file_content = f
                
                if file_name.lower().endswith(('.jpg', '.jpeg', '.png')):
                    try:
                        image = Image.open(f)
                        if image.mode != 'RGB':
                            image = image.convert('RGB')
                        
                        pdf_io = BytesIO()
                        image.save(pdf_io, format='PDF')
                        file_content = ContentFile(pdf_io.getvalue(), name=f"{os.path.splitext(file_name)[0]}.pdf")
                        file_name = f"{os.path.splitext(file_name)[0]}.pdf"
                    except Exception:
                        pass
                
                # Save Document
                BudgetRealignmentSupportingDocument.objects.create(
                    budget_realignment=realignment,
                    document=file_content,
                    file_name=file_name,
                    file_size=f.size,
                    uploaded_by=user
                )

            messages.success(self.request, "Budget Realignment request submitted successfully.")
            return redirect('create_budget_realignment')

        except DepartmentPRE.DoesNotExist:
            messages.error(self.request, "Invalid PRE selection.")
            return self.form_invalid(form)


@login_required
def get_realtime_line_item_amounts(request):
    """
    AJAX Endpoint to get quarterly breakdown for a selected line item.
    """
    pre_id = request.GET.get('pre_id')
    item_key = request.GET.get('item_key')
    
    if not pre_id or not item_key:
        return JsonResponse({'success': False, 'error': 'Missing params'})
        
    try:
        item = PRELineItem.objects.get(id=item_key, pre_id=pre_id)
        
        # Validate User Ownership
        if item.pre.submitted_by != request.user:
            return JsonResponse({'success': False, 'error': 'Unauthorized'})
            
        data = {}
        for q in ['Q1', 'Q2', 'Q3', 'Q4']:
            allocated = item.get_quarter_amount(q)
            consumed = item.get_quarter_consumed(q)
            reserved = item.get_quarter_reserved(q)
            
            # Pending Realignments
            pending_realign = PREBudgetRealignment.objects.filter(
                source_item_key=str(item.id),
                source_pre=item.pre,
                status__in=['Pending', 'Partially Approved', 'Awaiting Admin Verification']
            ).aggregate(
                total=Coalesce(Sum(f'{q.lower()}_amount'), Decimal('0'))
            )['total']
            
            remaining = allocated - consumed - reserved - pending_realign
            
            data[q.lower()] = {
                'allocated': float(allocated),
                'consumed': float(consumed),
                'reserved': float(reserved),
                'pending': float(pending_realign),
                'remaining': float(max(remaining, 0))
            }
            
        return JsonResponse({'success': True, 'quarters': data})
        
    except PRELineItem.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Item not found'})


class PreviewRealignmentView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = PREBudgetRealignment
    template_name = 'end_user_panel/preview_realignment_documents.html'
    context_object_name = 'realignment'
    
    def test_func(self):
        obj = self.get_object()
        return obj.requested_by == self.request.user or self.request.user.is_staff

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        realignment = self.object
        
        context['quarters'] = realignment.get_selected_quarters()
        context['supporting_documents'] = realignment.supporting_documents.filter(is_signed_copy=False)
        context['signed_documents'] = realignment.supporting_documents.filter(is_signed_copy=True)
        return context


class UploadSignedRealignmentDocView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return not self.request.user.is_staff

    def post(self, request, pk):
        realignment = get_object_or_404(PREBudgetRealignment, pk=pk, requested_by=request.user)
        
        if realignment.status != 'Partially Approved':
             messages.error(request, "Realignment is not in Partially Approved state.")
             return redirect('preview_realignment_documents', pk=pk)

        if 'signed_document' in request.FILES:
            f = request.FILES['signed_document']
            
            realignment.end_user_uploaded_document = f
            realignment.end_user_uploaded_at = timezone.now()
            realignment.status = 'Awaiting Admin Verification'
            realignment.save()
            
            messages.success(request, "Signed document uploaded successfully.")
        else:
            messages.error(request, "No file selected.")
            
        return redirect('preview_realignment_documents', pk=pk)
