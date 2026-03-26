from functools import wraps

from django.http import HttpResponseForbidden
from django.shortcuts import redirect


def role_required(role):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            if request.user.role != role:
                return HttpResponseForbidden("Access denied.")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


producer_required = role_required('producer')
customer_required = role_required('customer')
