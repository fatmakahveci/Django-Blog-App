"""Shared submission quotas, independent of cookies and application workers."""
from datetime import timedelta
from ipaddress import ip_address
from math import ceil

from django.db.models import F
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import SubmissionQuota


WINDOW_SECONDS = 600


def client_digest(request, scope):
    # Only the server's peer address is trusted, never client forwarding headers.
    try:
        address = ip_address(request.META.get('REMOTE_ADDR', ''))
        address = str(getattr(address, 'ipv4_mapped', None) or address)
    except ValueError:
        address = 'unknown'
    return salted_hmac(f'blog.{scope}-client', address, algorithm='sha256').hexdigest()


def submission_retry_after(request, scope, limit, *, using='default'):
    """Reserve a slot atomically; return zero on success or retry seconds."""
    now = timezone.now()
    key = client_digest(request, scope)
    quotas = SubmissionQuota.objects.using(using)
    _, created = quotas.get_or_create(key=key, defaults={'expires_at': now + timedelta(seconds=WINDOW_SECONDS)})
    if created:
        # Bound cleanup work and recheck expiry so an active quota is never deleted.
        expired = list(quotas.filter(expires_at__lte=now).values_list('pk', flat=True)[:100])
        quotas.filter(pk__in=expired, expires_at__lte=now).delete()
    quota = quotas.filter(pk=key)
    quota.filter(expires_at__lte=now).update(used=0, expires_at=now + timedelta(seconds=WINDOW_SECONDS))
    # A single conditional UPDATE prevents simultaneous requests exceeding the cap.
    if quota.filter(expires_at__gt=now, used__lt=limit).update(used=F('used') + 1):
        return 0
    expires_at = quota.values_list('expires_at', flat=True).first()
    return max(1, ceil((expires_at - now).total_seconds())) if expires_at else WINDOW_SECONDS
