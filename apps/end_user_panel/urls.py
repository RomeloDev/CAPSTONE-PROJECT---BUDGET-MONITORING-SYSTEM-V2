from django.urls import path
from .views import EndUserDashboardView
from . import views

urlpatterns = [
    path('dashboard/', EndUserDashboardView.as_view(), name='user_dashboard'),
    path('department-pre/', views.DepartmentPREPageView.as_view(), name='department_pre_page'),
    
    # Placeholder for the Upload Action (to be implemented next)
    path('upload-pre/<int:allocation_id>/', views.UploadPREView.as_view(), name='upload_pre'),
    
    path('preview-pre/<uuid:pre_id>/', views.PreviewPREView.as_view(), name='preview_pre'),
    path('view-pre/<uuid:pre_id>/', views.ViewPREDetailView.as_view(), name='view_pre_detail'),
    
    # Placeholder for Template Download
    # path('download-template/', views.download_pre_template, name='download_pre_template'),
    
    path('pre/<uuid:pre_id>/upload-signed-docs/', views.upload_approved_pre_documents, name='upload_approved_pre_documents'),
    path('budget/overview/', views.budget_overview, name='budget_overview'),
    path('budget/pre-details/', views.pre_budget_details, name='pre_budget_details'),
    path('budget/quarterly/', views.quarterly_analysis, name='quarterly_analysis'),
    path('budget/history/', views.transaction_history, name='transaction_history'),
    path('budget/reports/', views.budget_reports, name='budget_reports'),
    path('pr-ad-requests/', views.pr_ad_list, name='pr_ad_list'),
    path('pr-ad-request/purchase_request_upload/', views.purchase_request_upload, name='purchase_request_upload'),
    path('get-pre-line-items/', views.get_pre_line_items, name='get_pre_line_items'),
    path('pr/view/<uuid:pr_id>/', views.ViewPRDetailView.as_view(), name='view_pr_detail'),
    path('pr/<uuid:pr_id>/upload-signed-docs/', views.upload_signed_pr_docs, name='upload_signed_pr_docs'),
    path('ad/upload/', views.activity_design_upload, name='activity_design_upload'),
    path('ad/view/<uuid:ad_id>/', views.ActivityDesignDetailView.as_view(), name='view_ad_detail'),
    path('ad/<uuid:ad_id>/upload-signed-docs/', views.upload_signed_ad_docs, name='upload_signed_ad_docs'),
]
