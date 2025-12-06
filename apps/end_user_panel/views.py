from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView
from django.db.models import Sum, Q
from apps.budgets.models import PurchaseRequest, ActivityDesign, BudgetAllocation, DepartmentPRE

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
