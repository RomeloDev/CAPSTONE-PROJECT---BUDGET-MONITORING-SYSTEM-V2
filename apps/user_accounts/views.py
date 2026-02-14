from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import LoginForm, UserUpdateForm, CustomPasswordChangeForm
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

@login_required
def settings_view(request):
    """
    Unified Settings View for both Admin and End Users.
    Handles Profile Update and Password Change via HTMX or standard POST.
    """
    # Determine base template based on user role
    if request.user.is_superuser or request.user.is_staff:
        base_template = 'admin_base_template/dashboard.html'
    else:
        base_template = 'end_user_base_template/dashboard.html'

    user = request.user
    profile_form = UserUpdateForm(instance=user)
    password_form = CustomPasswordChangeForm(user)

    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        
        if form_type == 'profile_update':
            profile_form = UserUpdateForm(request.POST, instance=user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Profile updated successfully.")
            else:
                messages.error(request, "Please correct the errors below.")
        
        elif form_type == 'password_change':
            password_form = CustomPasswordChangeForm(user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)  # Important!
                messages.success(request, "Password changed successfully.")
                # Re-initialize form to clear fields
                password_form = CustomPasswordChangeForm(user)
            else:
                messages.error(request, "Please correct the errors below.")
        
        # If HTMX request, return only the forms partial with messages
        if request.headers.get('HX-Request'):
            return render(request, 'partials/settings_forms.html', {
                'profile_form': profile_form,
                'password_form': password_form,
            })

    context = {
        'base_template': base_template,
        'profile_form': profile_form,
        'password_form': password_form,
    }
    return render(request, 'common/settings.html', context)