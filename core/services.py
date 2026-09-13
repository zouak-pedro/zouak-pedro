from django.contrib.contenttypes.models import ContentType

from .models import AuditLog

class AuditLogService:
    Action = AuditLog.Action

    @staticmethod
    def log(*, action, actor=None, clinic=None, target=None, object_repr="",
             path="", method="", status_code=None, ip_address=None):
        content_type = None
        object_id = None

        if target is not None:
            content_type = ContentType.objects.get_for_model(target)
            object_id = target.pk
            if not object_repr:
                object_repr = str(target)[:255]

        AuditLog.objects.create(
            clinic=clinic,
            actor=actor,
            actor_email=getattr(actor, "email", "") or "",
            action=action,
            content_type=content_type,
            object_id=object_id,
            object_repr=object_repr,
            path=path,
            method=method,
            status_code=status_code,
            ip_address=ip_address,
        )

    @staticmethod
    def get_all(filters=None):
        qs = AuditLog.objects.select_related("actor", "clinic", "content_type").all()
        filters = filters or {}

        if filters.get("action"):
            qs = qs.filter(action=filters["action"])
        if filters.get("actor_email"):
            qs = qs.filter(actor_email__icontains=filters["actor_email"])
        if filters.get("start_date"):
            qs = qs.filter(created_at__date__gte=filters["start_date"])
        if filters.get("end_date"):
            qs = qs.filter(created_at__date__lte=filters["end_date"])

        return qs

    @staticmethod
    def _get_ip(request):
        if request is None:
            return None
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")