from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from .forms import LoginForm

class AdminLoginView(LoginView):
    template_name = 'user_accounts/admin_login.html'
    
    form_class = LoginForm
    
    def get_success_url(self):
        return reverse_lazy('admin_dashboard')

class EndUserLoginView(LoginView):
    template_name = 'user_accounts/end_user_login.html'
    
    form_class = LoginForm
    
    def get_success_url(self):
        return reverse_lazy('user_dashboard')

def logout_view(request):
    """
    Custom logout view to handle GET requests (deprecated in Django 5.0+ default LogoutView).
    """
    logout(request)
    # Redirect to admin login if the user was on the admin side (simple heuristic)
    if 'admin' in request.path:
         return redirect('admin_login')
    return redirect('end_user_login')