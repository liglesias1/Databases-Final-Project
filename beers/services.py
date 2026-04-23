"""
Business logic extracted from models.py.

Keeps models focused on schema/fields and makes logic easier to test.
"""

from datetime import timedelta
from django.utils import timezone


def compute_current_streak(user):
    """Consecutive days with at least 1 check-in, ending today."""
    today = timezone.now().date()
    dates = set(user.checkins.values_list("created_at__date", flat=True))
    streak = 0
    day = today
    while day in dates:
        streak += 1
        day -= timedelta(days=1)
    return streak


def compute_longest_streak(user):
    """Longest consecutive day streak in user's history."""
    dates = sorted(set(user.checkins.values_list("created_at__date", flat=True)))
    if not dates:
        return 0
    longest = current = 1
    for i in range(1, len(dates)):
        if (dates[i] - dates[i - 1]).days == 1:
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return longest


def check_and_award_badges(user):
    """Award any newly earned badges. Call after every check-in."""
    from .models import Badge, UserBadge

    for badge in Badge.objects.all():
        if badge.is_earned_by(user):
            UserBadge.objects.get_or_create(user=user, badge=badge)


def get_recommendations(user, limit=6):
    """
    Recommend beers based on the user's style history.

    Strategy: find styles the user rates highest, then suggest top-rated
    beers in those styles that the user hasn't tried yet.
    """
    from django.db.models import Avg, Count
    from .models import Beer, CheckIn

    # Get user's top-rated styles (at least 2 check-ins in the style)
    tried_beer_ids = set(
        user.checkins.values_list("beer_id", flat=True)
    )
    if not tried_beer_ids:
        # Cold start: return top-rated beers overall
        return Beer.objects.select_related("style", "brewery").order_by("-avg_rating")[:limit]

    top_styles = (
        CheckIn.objects.filter(user=user)
        .values("beer__style_id")
        .annotate(avg=Avg("rating"), n=Count("id"))
        .filter(n__gte=2)
        .order_by("-avg", "-n")[:5]
    )
    style_ids = [s["beer__style_id"] for s in top_styles]

    if not style_ids:
        # Not enough data — use all styles the user has tried
        style_ids = list(
            user.checkins.values_list("beer__style_id", flat=True).distinct()
        )

    return (
        Beer.objects.filter(style_id__in=style_ids)
        .exclude(id__in=tried_beer_ids)
        .select_related("style", "brewery")
        .order_by("-avg_rating")[:limit]
    )


def get_trending_beers(days=7, limit=10):
    """
    Beers with the most check-ins in the last N days.
    """
    from django.db.models import Count
    from .models import Beer

    cutoff = timezone.now() - timedelta(days=days)
    return (
        Beer.objects.filter(checkins__created_at__gte=cutoff)
        .annotate(recent_checkins=Count("checkins"))
        .select_related("style", "brewery")
        .order_by("-recent_checkins")[:limit]
    )


def get_similar_drinkers(user, limit=5):
    """
    Find users with the most overlapping beer history.
    """
    from django.contrib.auth.models import User
    from django.db.models import Count, Q

    my_beer_ids = set(user.checkins.values_list("beer_id", flat=True))
    if not my_beer_ids:
        return []

    return (
        User.objects.filter(checkins__beer_id__in=my_beer_ids)
        .exclude(id=user.id)
        .annotate(
            overlap=Count(
                "checkins__beer_id", distinct=True,
                filter=Q(checkins__beer_id__in=my_beer_ids),
            )
        )
        .order_by("-overlap")[:limit]
    )
