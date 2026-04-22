from functools import wraps
from django.shortcuts import redirect
from django.http import HttpResponseForbidden
from .models import ManufacturerMembership


def manufacturer_required(roles=None):
    """Require user to be a manufacturer member. Optionally restrict to specific roles."""

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("login")
            membership = ManufacturerMembership.objects.filter(
                user=request.user
            ).select_related("manufacturer").first()
            if not membership:
                return redirect("login")
            if roles and membership.role not in roles:
                return HttpResponseForbidden("Insufficient permissions.")
            request.manufacturer = membership.manufacturer
            request.manufacturer_role = membership.role
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
