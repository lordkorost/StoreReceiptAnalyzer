from django.shortcuts import redirect
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()

class FirstRunMiddleware:
    """
    Middleware that checks if it is the app's first run.
    If there are no superusers, redirects to the setup page.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # URLs that must be accessible even without superuser privileges
        self.allowed_urls = [
            reverse('setup'),
            reverse('admin:login'),
            '/static/',  
            '/media/', 
        ]

    def __call__(self, request):
        # Check if superusers exist
        if not User.objects.filter(is_superuser=True).exists():
            # If the current URL is not in the allowlist, redirect to setup
            if not any(request.path.startswith(url) for url in self.allowed_urls):
                return redirect('setup')
        
        response = self.get_response(request)
        return response