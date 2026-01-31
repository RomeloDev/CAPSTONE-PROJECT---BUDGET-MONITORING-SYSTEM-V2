from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from .forms import LoginForm
from apps.admin_panel.utils import log_activity
from django.contrib.auth.views import PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView

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

def logout_view(request):
    """
    Custom logout view to handle GET requests (deprecated in Django 5.0+ default LogoutView).
    """
    log_activity(
        user=request.user,
        action='LOGOUT',
        detail=f"End User {request.user} has been logout successfully.",
        model_name='User',
        record_id=request.user.pk,
        request=request
    )
    
    logout(request)
    
    # Redirect to admin login if the user was on the admin side (simple heuristic)
    if 'admin' in request.path:
         return redirect('admin_login')
    return redirect('end_user_login')

class CustomPasswordResetView(PasswordResetView):
    template_name = 'user_accounts/registration/password_reset_form.html'
    email_template_name = 'user_accounts/registration/password_reset_email.html'
    success_url = reverse_lazy('password_reset_done')
class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'user_accounts/registration/password_reset_done.html'
class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'user_accounts/registration/password_reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')
class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'user_accounts/registration/password_reset_complete.html'