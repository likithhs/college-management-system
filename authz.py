from functools import wraps
from flask import abort, flash, redirect, url_for, request
from flask_login import current_user
from models import ModuleConfig

def check_tenant_ownership(resource_college_id):
    """
    Reusable helper to verify if the current authenticated user has ownership
    over a tenant-bound resource based on college_id.
    """
    if not current_user or not current_user.is_authenticated:
        return False
    if current_user.is_super_admin:
        return True
    if current_user.college_id is None:
        return False
    return current_user.college_id == resource_college_id

def platform_super_admin_required(f):
    """
    Decorator enforcing that the current user is authenticated and possesses
    the PLATFORM_SUPER_ADMIN role. Returns HTTP 403 Forbidden otherwise.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login', next=request.path))
        if not current_user.is_super_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def college_admin_required(f):
    """
    Decorator enforcing that the current user is authenticated and is a COLLEGE_ADMIN
    (or PLATFORM_SUPER_ADMIN). Returns HTTP 403 Forbidden otherwise.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login', next=request.path))
        if not (current_user.is_college_admin or current_user.is_super_admin):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def module_admin_required(module_key):
    """
    Parameterized decorator verifying that a College Admin's assigned tenant has
    admin_access = True for the target module_key.
    Returns HTTP 403 Forbidden if admin_access is disabled or tenant mismatch occurs.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('login', next=request.path))
            
            # Platform Super Admin bypass for platform oversight
            if current_user.is_super_admin:
                return f(*args, **kwargs)
                
            if not current_user.is_college_admin:
                abort(403)
                
            college_id = current_user.college_id
            if not college_id:
                abort(403)
                
            # Query tenant-specific ModuleConfig in database
            cfg = ModuleConfig.query.filter_by(college_id=college_id, module_key=module_key).first()
            if not cfg or not cfg.enabled or not cfg.admin_access:
                abort(403)
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator
