from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from .forms import LoginForm
from apps.admin_panel.utils import log_activity

class AdminLoginView(LoginView):
    template_name = 'user_accounts/admin_login.html'
    
    form_class = LoginForm
    
    def get_success_url(self):
        
        log_activity(
            user=self.request.user,
            action='LOGIN',
            detail=f"Admin logged in successfully.",
            model_name='User',
            record_id=self.request.user.pk,
            request=self.request
        )
        
        return reverse_lazy('admin_dashboard')

class EndUserLoginView(LoginView):
    template_name = 'user_accounts/end_user_login.html'
    
    form_class = LoginForm
    
    def get_success_url(self):
        
        log_activity(
            user=self.request.user,
            action='LOGIN',
            detail=f"End User {self.request.user} logged in successfully.",
            model_name='User',
            record_id=self.request.user.pk,
            request=self.request
        )
        
        return reverse_lazy('user_dashboard')

def logout_view(self, request):
    """
    Custom logout view to handle GET requests (deprecated in Django 5.0+ default LogoutView).
    """
    logout(request)
    
    log_activity(
            user=self.request.user,
            action='LOGOUT',
            detail=f"End User {self.request.user} has been logout successfully.",
            model_name='User',
            record_id=self.request.user.pk,
            request=self.request
        )
    
    # Redirect to admin login if the user was on the admin side (simple heuristic)
    if 'admin' in request.path:
         return redirect('admin_login')
    return redirect('end_user_login')