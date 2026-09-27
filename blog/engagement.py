"""Anonymous reader feedback; the signed cookie contains no personal details."""
import re
from uuid import uuid4

from django.conf import settings
from django.db.models import Count
from django.utils.crypto import salted_hmac

from .models import Poll, Reaction


READER_COOKIE = 'folio_reader'
READER_SALT = 'folio.reader.v1'
READER_MAX_AGE = 60 * 60 * 24 * 365


def reader_identity(request, create=False):
    token = request.get_signed_cookie(READER_COOKIE, default='', salt=READER_SALT, max_age=READER_MAX_AGE)
    valid = re.fullmatch(r'[a-f0-9]{32}', token) is not None
    if not valid:
        token = uuid4().hex if create else ''
    digest = salted_hmac(READER_SALT, token, algorithm='sha256').hexdigest() if token else ''
    return digest, token if not valid and create else None


def remember_reader(response, token):
    if token:
        response.set_signed_cookie(READER_COOKIE, token, salt=READER_SALT, max_age=READER_MAX_AGE,
                                   httponly=True, secure=not settings.DEBUG, samesite='Lax')
    return response


def engagement_context(post, request):
    digest, _ = reader_identity(request)
    totals = dict(post.reactions.values('kind').annotate(total=Count('pk')).values_list('kind', 'total'))
    selected = post.reactions.filter(reader_digest=digest).values_list('kind', flat=True).first() if digest else None
    poll = Poll.objects.filter(post=post).first()
    options = list(poll.choices.annotate(vote_count=Count('votes'))) if poll else []
    votes = sum(option.vote_count for option in options)
    choice = poll.votes.filter(reader_digest=digest).values_list('choice_id', flat=True).first() if poll and digest else None
    for option in options:
        option.percent = round(option.vote_count / votes * 100) if votes else 0
    return {
        'reactions': [{'kind': kind, 'label': label, 'count': totals.get(kind, 0), 'selected': kind == selected}
                      for kind, label in Reaction.Kind.choices],
        'selected_reaction': selected,
        'poll': poll if len(options) >= 2 else None,
        'poll_options': options, 'poll_total': votes, 'poll_choice': choice,
    }
