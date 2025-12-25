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
]
