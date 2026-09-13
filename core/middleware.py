from .context import (set_current_clinic, clear_current_clinic,
                      set_current_user, clear_current_user)
from .services import AuditLogService
from django.conf import settings
from django.utils import translation

class CurrentClinicMiddleware:
    """
    Stashes request.user.clinic in a context var for the duration of the request,
    so ClinicManager can auto-scope querysets without every view/service 
    having to pass `clinic` explicitly.

    Django admin is deliberately  left unscoped  (context var stays None)
    since it's platform-staff tooling, not clinic-user tooling.

    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        is_admin_path = request.path.startswith(f"/{settings.ADMIN_URL if hasattr(settings, 'ADMIN_URL') else 'admin'}/")

        if not is_admin_path:
            clinic = getattr(getattr(request, "user", None), "clinic", None)
            set_current_clinic(clinic)

        try:
            response = self.get_response(request)
        finally:
            clear_current_clinic()

        return response

EXCLUDED_AUDIT_PREFIXES = ("/static/", "/media/", "/admin/jsi18n/")

class AuditTrailMiddleware:
    """
    Logs every authenticated request as a generic access-trail entry
    (path, method, status, actor, clinic, IP) — the "full trail" layer
    on top of the structured CREATE/UPDATE/PRINT/LOGIN events logged
    elsewhere via signals and explicit calls.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        is_authenticated = bool(user and user.is_authenticated)

        if is_authenticated:
            set_current_user(user)

        response = self.get_response(request)

        if is_authenticated and not request.path.startswith(EXCLUDED_AUDIT_PREFIXES):
            AuditLogService.log(
                actor=user,
                clinic=getattr(user, "clinic", None),
                action=AuditLogService.Action.VIEW,
                path=request.path,
                method=request.method,
                status_code=response.status_code,
                ip_address=AuditLogService._get_ip(request),
            )

        clear_current_user()

        return response


class UserLanguageMiddleware:
    """
    Activates the translation for the logged-in user's saved language
    preference (accounts.User.language). For anonymous requests, falls
    back to a session-stored choice (set via the top-nav language
    switcher on pages like the landing page), then finally to the
    browser's Accept-Language header.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        language = None

        if user and user.is_authenticated and getattr(user, "language", None):
            language = user.language

        if not language:
            language = request.session.get("language")

        if not language:
            language = translation.get_language_from_request(request)

        translation.activate(language)
        request.LANGUAGE_CODE = translation.get_language()

        try:
            response = self.get_response(request)
        finally:
            translation.deactivate()

        return response