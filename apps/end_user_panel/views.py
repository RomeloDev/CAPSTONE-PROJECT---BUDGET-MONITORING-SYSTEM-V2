from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView
from django.db.models import Sum, Q
from django.contrib import messages
from django.views import View
from decimal import Decimal
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
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
    PREDraftSupportingDocument
)
# Note: PREDraft and PREDraftSupportingDocument are used for draft management
# DepartmentPRE is created only on final submission in PreviewPREView
from apps.end_user_panel.utils.pre_parser_dynamic import parse_pre_excel_dynamic
import json
import os

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
        total_remaining = stats['total_remaining'] or 0
        
        context['total_allocated'] = total_allocated
        context['total_used'] = total_used
        context['total_remaining'] = total_remaining
        
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

        # --- 4. Quarterly Data (Mocked for UI consistency for now) ---
        # TODO: Implement actual quarterly aggregation logic
        context['quarterly_data'] = [
            {'quarter': 'Q1', 'allocated': total_allocated / 4, 'consumed': total_used / 4, 'utilization': context['utilization_percentage']},
            {'quarter': 'Q2', 'allocated': total_allocated / 4, 'consumed': 0, 'utilization': 0},
            {'quarter': 'Q3', 'allocated': total_allocated / 4, 'consumed': 0, 'utilization': 0},
            {'quarter': 'Q4', 'allocated': total_allocated / 4, 'consumed': 0, 'utilization': 0},
        ]

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
        ).select_related('approved_budget').order_by('-allocated_at')
        
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