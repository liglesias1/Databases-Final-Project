import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Q, Count, Avg, Sum
from django.core.paginator import Paginator
from django.http import JsonResponse
from .models import (
    Beer, BeerStyle, Brewery, CheckIn, Challenge, UserProfile,
    Follow, Badge, UserBadge, check_and_award_badges,
)


def beer_list(request):
    beers = Beer.objects.select_related("style", "brewery").all()
    q = request.GET.get("q", "").strip()
    style_id = request.GET.get("style", "")
    min_abv = request.GET.get("min_abv", "")
    max_abv = request.GET.get("max_abv", "")
    sort = request.GET.get("sort", "name")

    if q:
        beers = beers.filter(
            Q(name__icontains=q) | Q(brewery__name__icontains=q) | Q(style__name__icontains=q)
        )
    if style_id:
        beers = beers.filter(style_id=style_id)
    if min_abv:
        try:
            beers = beers.filter(abv__gte=float(min_abv))
        except ValueError:
            pass
    if max_abv:
        try:
            beers = beers.filter(abv__lte=float(max_abv))
        except ValueError:
            pass

    sort_options = {"name": "name", "rating": "-avg_rating", "abv": "-abv", "bitter": "-bitter"}
    beers = beers.order_by(sort_options.get(sort, "name"))

    paginator = Paginator(beers, 24)
    beers_page = paginator.get_page(request.GET.get("page"))

    tried_ids = set()
    if request.user.is_authenticated:
        tried_ids = set(request.user.checkins.values_list("beer_id", flat=True))

    return render(request, "beers/beer_list.html", {
        "beers": beers_page, "styles": BeerStyle.objects.all(),
        "q": q, "style_id": style_id, "min_abv": min_abv, "max_abv": max_abv,
        "sort": sort, "tried_ids": tried_ids,
    })


def beer_detail(request, pk):
    beer = get_object_or_404(Beer.objects.select_related("style", "brewery"), pk=pk)
    user_checkin = None
    if request.user.is_authenticated:
        user_checkin = CheckIn.objects.filter(user=request.user, beer=beer).first()
    recent_checkins = beer.checkins.select_related("user").order_by("-created_at")[:10]
    similar_beers = Beer.objects.filter(style=beer.style).exclude(pk=beer.pk)[:6]
    return render(request, "beers/beer_detail.html", {
        "beer": beer, "user_checkin": user_checkin,
        "recent_checkins": recent_checkins, "similar_beers": similar_beers,
    })


@login_required
def checkin(request, beer_id):
    beer = get_object_or_404(Beer, pk=beer_id)
    if request.method == "POST":
        rating = int(request.POST.get("rating", 3))
        quantity = int(request.POST.get("quantity", 1))
        notes = request.POST.get("notes", "").strip()
        CheckIn.objects.create(
            user=request.user, beer=beer,
            rating=rating, quantity=quantity, notes=notes,
        )
        check_and_award_badges(request.user)
        messages.success(request, f"Logged {quantity}x {beer.name}. Cheers!")
        return redirect("beer_detail", pk=beer.pk)
    return redirect("beer_detail", pk=beer.pk)


def leaderboard(request):
    top_by_count = (
        UserProfile.objects.annotate(n=Count("user__checkins"))
        .filter(n__gt=0).order_by("-n")[:20]
    )
    top_by_drinks = (
        UserProfile.objects.annotate(n=Sum("user__checkins__quantity"))
        .filter(n__gt=0).order_by("-n")[:20]
    )
    top_by_styles = (
        UserProfile.objects.annotate(n=Count("user__checkins__beer__style", distinct=True))
        .filter(n__gt=0).order_by("-n")[:20]
    )
    top_by_countries = (
        UserProfile.objects.annotate(n=Count("user__checkins__beer__brewery__country", distinct=True))
        .filter(n__gt=0).order_by("-n")[:20]
    )
    top_by_followers = (
        UserProfile.objects.annotate(n=Count("user__followers"))
        .filter(n__gt=0).order_by("-n")[:20]
    )
    return render(request, "beers/leaderboard.html", {
        "top_by_count": top_by_count,
        "top_by_drinks": top_by_drinks,
        "top_by_styles": top_by_styles,
        "top_by_countries": top_by_countries,
        "top_by_followers": top_by_followers,
    })


def style_list(request):
    styles = BeerStyle.objects.annotate(n=Count("beers")).order_by("family", "name")
    families = {}
    for s in styles:
        families.setdefault(s.family or "Other", []).append(s)
    return render(request, "beers/style_list.html", {"families": families.items()})


def style_detail(request, pk):
    style = get_object_or_404(BeerStyle, pk=pk)
    beers = style.beers.select_related("brewery").order_by("-avg_rating")[:48]
    return render(request, "beers/style_detail.html", {"style": style, "beers": beers})


def passport(request, username=None):
    if username:
        target_user = get_object_or_404(User, username=username)
    elif request.user.is_authenticated:
        target_user = request.user
    else:
        return redirect("login")

    profile = target_user.profile
    is_own = target_user == request.user
    is_following = False
    if request.user.is_authenticated and not is_own:
        is_following = Follow.objects.filter(
            follower=request.user, followed=target_user
        ).exists()

    # Stats
    checkins = target_user.checkins.select_related("beer", "beer__style", "beer__brewery")
    total_drinks = checkins.aggregate(total=Sum("quantity"))["total"] or 0
    avg_rating = checkins.aggregate(avg=Avg("rating"))["avg"]

    # Style completion grid
    all_styles = BeerStyle.objects.annotate(
        total_beers=Count("beers")
    ).order_by("family", "name")
    tried_style_ids = set(
        checkins.values_list("beer__style_id", flat=True).distinct()
    )
    tried_style_counts = dict(
        checkins.values("beer__style_id")
        .annotate(n=Count("beer", distinct=True))
        .values_list("beer__style_id", "n")
    )

    style_grid = []
    families_grid = {}
    for style in all_styles:
        entry = {
            "style": style,
            "tried": style.id in tried_style_ids,
            "tried_count": tried_style_counts.get(style.id, 0),
            "total_count": style.total_beers,
        }
        style_grid.append(entry)
        families_grid.setdefault(style.family or "Other", []).append(entry)

    total_styles = all_styles.count()
    styles_tried = len(tried_style_ids)
    completion_pct = int((styles_tried / total_styles) * 100) if total_styles else 0

    # Badges
    all_badges = Badge.objects.all()
    earned_ids = set(
        UserBadge.objects.filter(user=target_user).values_list("badge_id", flat=True)
    )
    earned_badges_qs = UserBadge.objects.filter(user=target_user).select_related("badge")
    badge_list = []
    for badge in all_badges:
        earned_obj = None
        for ub in earned_badges_qs:
            if ub.badge_id == badge.id:
                earned_obj = ub
                break
        badge_list.append({
            "badge": badge,
            "earned": badge.id in earned_ids,
            "earned_at": earned_obj.earned_at if earned_obj else None,
        })

    # Timeline (paginated)
    timeline_qs = checkins.order_by("-created_at")
    paginator = Paginator(timeline_qs, 20)
    timeline_page = paginator.get_page(request.GET.get("page"))

    # Style breakdown
    style_breakdown = (
        checkins.values("beer__style__name")
        .annotate(count=Count("id"), avg=Avg("rating"), drinks=Sum("quantity"))
        .order_by("-count")[:10]
    )

    return render(request, "beers/passport.html", {
        "target_user": target_user,
        "profile": profile,
        "is_own": is_own,
        "is_following": is_following,
        # Stats
        "total_drinks": total_drinks,
        "avg_rating": avg_rating,
        "styles_tried": styles_tried,
        "total_styles": total_styles,
        "completion_pct": completion_pct,
        # Grid
        "families_grid": families_grid.items(),
        # Badges
        "badge_list": badge_list,
        "earned_count": len(earned_ids),
        "total_badges": all_badges.count(),
        # Timeline
        "timeline": timeline_page,
        # Breakdown
        "style_breakdown": style_breakdown,
    })


@login_required
def follow_user(request, username):
    target = get_object_or_404(User, username=username)
    if target != request.user:
        Follow.objects.get_or_create(follower=request.user, followed=target)
        check_and_award_badges(request.user)
        messages.success(request, f"Following {target.username}")
    return redirect("user_passport", username=username)


@login_required
def unfollow_user(request, username):
    target = get_object_or_404(User, username=username)
    Follow.objects.filter(follower=request.user, followed=target).delete()
    messages.success(request, f"Unfollowed {target.username}")
    return redirect("user_passport", username=username)


@login_required
def activity_feed(request):
    following_ids = request.user.following.values_list("followed_id", flat=True)
    feed = (
        CheckIn.objects.filter(user_id__in=following_ids)
        .select_related("user", "beer", "beer__style", "beer__brewery")
        .order_by("-created_at")
    )
    paginator = Paginator(feed, 30)
    feed_page = paginator.get_page(request.GET.get("page"))

    return render(request, "beers/activity_feed.html", {"feed": feed_page})


def user_search(request):
    q = request.GET.get("q", "").strip()
    users = []
    if q:
        users = User.objects.filter(
            Q(username__icontains=q)
        ).select_related("profile").annotate(
            beer_count=Count("checkins__beer", distinct=True)
        )[:30]

    following_ids = set()
    if request.user.is_authenticated:
        following_ids = set(
            request.user.following.values_list("followed_id", flat=True)
        )

    return render(request, "beers/user_search.html", {
        "q": q, "users": users, "following_ids": following_ids,
    })


def profile(request, username=None):
    """Redirect old profile URLs to passport."""
    if username:
        return redirect("user_passport", username=username)
    return redirect("passport")


def register(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome to BeerPass, {user.username}!")
            return redirect("beer_list")
    else:
        form = UserCreationForm()
    return render(request, "registration/register.html", {"form": form})


def _build_heatmap_data(checkins_qs):
    """Build heatmap data from a check-in queryset."""
    data = (
        checkins_qs
        .exclude(beer__brewery__latitude=None)
        .values("beer__brewery__latitude", "beer__brewery__longitude")
        .annotate(intensity=Sum("quantity"))
        .order_by("-intensity")
    )
    return [
        [float(d["beer__brewery__latitude"]), float(d["beer__brewery__longitude"]), d["intensity"]]
        for d in data
    ]


def _build_brewery_markers():
    """Build brewery marker data with check-in counts."""
    breweries = (
        Brewery.objects.exclude(latitude=None)
        .annotate(
            beer_count=Count("beers"),
            checkin_count=Count("beers__checkins"),
        )
        .filter(checkin_count__gt=0)
        .order_by("-checkin_count")
    )
    markers = []
    for b in breweries:
        top_beer = (
            Beer.objects.filter(brewery=b)
            .annotate(n=Count("checkins"))
            .order_by("-n")
            .values_list("name", flat=True)
            .first()
        )
        markers.append({
            "name": b.name,
            "country": b.country,
            "city": b.city,
            "lat": float(b.latitude),
            "lng": float(b.longitude),
            "beers": b.beer_count,
            "checkins": b.checkin_count,
            "top_beer": top_beer or "",
        })
    return markers


def beer_map(request):
    """Consumption heatmap page."""
    all_checkins = CheckIn.objects.all()
    heatmap_data = _build_heatmap_data(all_checkins)

    my_heatmap_data = []
    if request.user.is_authenticated:
        my_heatmap_data = _build_heatmap_data(
            CheckIn.objects.filter(user=request.user)
        )

    brewery_markers = _build_brewery_markers()

    stats = {
        "total_countries": (
            CheckIn.objects.exclude(beer__brewery__country="")
            .values("beer__brewery__country").distinct().count()
        ),
        "total_breweries": (
            CheckIn.objects.values("beer__brewery").distinct().count()
        ),
        "total_checkins": CheckIn.objects.count(),
    }

    styles = BeerStyle.objects.annotate(n=Count("beers__checkins")).filter(n__gt=0).order_by("name")

    return render(request, "beers/map.html", {
        "heatmap_data": json.dumps(heatmap_data),
        "my_heatmap_data": json.dumps(my_heatmap_data),
        "brewery_markers": json.dumps(brewery_markers),
        "stats": stats,
        "styles": styles,
    })


def beer_map_data(request):
    """JSON endpoint for filtered heatmap data."""
    view = request.GET.get("view", "all")
    style_id = request.GET.get("style", "")

    qs = CheckIn.objects.all()
    if view == "mine" and request.user.is_authenticated:
        qs = qs.filter(user=request.user)
    if style_id:
        qs = qs.filter(beer__style_id=style_id)

    return JsonResponse({"heatmap": _build_heatmap_data(qs)})
