from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.db.models import Q, Count, Avg
from django.core.paginator import Paginator
from .models import Beer, BeerStyle, Brewery, CheckIn, Challenge, UserProfile


def beer_list(request):
    """Main beer catalog with search and filters."""
    beers = Beer.objects.select_related("style", "brewery").all()

    q = request.GET.get("q", "").strip()
    style_id = request.GET.get("style", "")
    min_abv = request.GET.get("min_abv", "")
    max_abv = request.GET.get("max_abv", "")
    sort = request.GET.get("sort", "name")

    if q:
        beers = beers.filter(
            Q(name__icontains=q)
            | Q(brewery__name__icontains=q)
            | Q(style__name__icontains=q)
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

    sort_options = {
        "name": "name",
        "rating": "-avg_rating",
        "abv": "-abv",
        "bitter": "-bitter",
    }
    beers = beers.order_by(sort_options.get(sort, "name"))

    paginator = Paginator(beers, 24)
    page = request.GET.get("page")
    beers_page = paginator.get_page(page)

    # Tried beer IDs for current user (to show "tried" badge)
    tried_ids = set()
    if request.user.is_authenticated:
        tried_ids = set(request.user.checkins.values_list("beer_id", flat=True))

    context = {
        "beers": beers_page,
        "styles": BeerStyle.objects.all(),
        "q": q,
        "style_id": style_id,
        "min_abv": min_abv,
        "max_abv": max_abv,
        "sort": sort,
        "tried_ids": tried_ids,
    }
    return render(request, "beers/beer_list.html", context)


def beer_detail(request, pk):
    """Individual beer page."""
    beer = get_object_or_404(
        Beer.objects.select_related("style", "brewery"), pk=pk
    )
    user_checkin = None
    if request.user.is_authenticated:
        user_checkin = CheckIn.objects.filter(user=request.user, beer=beer).first()

    recent_checkins = beer.checkins.select_related("user").order_by("-created_at")[:10]

    similar_beers = Beer.objects.filter(style=beer.style).exclude(pk=beer.pk)[:6]

    return render(
        request,
        "beers/beer_detail.html",
        {
            "beer": beer,
            "user_checkin": user_checkin,
            "recent_checkins": recent_checkins,
            "similar_beers": similar_beers,
        },
    )


@login_required
def checkin(request, beer_id):
    """Create or update a check-in."""
    beer = get_object_or_404(Beer, pk=beer_id)
    if request.method == "POST":
        rating = int(request.POST.get("rating", 3))
        notes = request.POST.get("notes", "").strip()
        checkin_obj, created = CheckIn.objects.update_or_create(
            user=request.user,
            beer=beer,
            defaults={"rating": rating, "notes": notes},
        )
        action = "logged" if created else "updated"
        messages.success(request, f"You {action} {beer.name}. Cheers!")
        return redirect("beer_detail", pk=beer.pk)
    return redirect("beer_detail", pk=beer.pk)


def leaderboard(request):
    """Top drinkers by count, styles, and countries."""
    top_by_count = (
        UserProfile.objects.annotate(n=Count("user__checkins"))
        .filter(n__gt=0)
        .order_by("-n")[:20]
    )
    top_by_styles = (
        UserProfile.objects.annotate(
            n=Count("user__checkins__beer__style", distinct=True)
        )
        .filter(n__gt=0)
        .order_by("-n")[:20]
    )
    top_by_countries = (
        UserProfile.objects.annotate(
            n=Count("user__checkins__beer__brewery__country", distinct=True)
        )
        .filter(n__gt=0)
        .order_by("-n")[:20]
    )

    return render(
        request,
        "beers/leaderboard.html",
        {
            "top_by_count": top_by_count,
            "top_by_styles": top_by_styles,
            "top_by_countries": top_by_countries,
        },
    )


def style_list(request):
    """All styles grouped by family."""
    styles = BeerStyle.objects.annotate(n=Count("beers")).order_by("family", "name")
    families = {}
    for s in styles:
        families.setdefault(s.family or "Other", []).append(s)
    return render(
        request, "beers/style_list.html", {"families": families.items()}
    )


def style_detail(request, pk):
    """Beers in a given style."""
    style = get_object_or_404(BeerStyle, pk=pk)
    beers = style.beers.select_related("brewery").order_by("-avg_rating")[:48]
    return render(
        request, "beers/style_detail.html", {"style": style, "beers": beers}
    )


@login_required
def profile(request, username=None):
    """User profile with check-in history and stats."""
    if username:
        target = get_object_or_404(UserProfile, user__username=username)
    else:
        target = request.user.profile

    checkins = target.user.checkins.select_related(
        "beer", "beer__style", "beer__brewery"
    )[:50]

    # Style breakdown
    style_breakdown = (
        target.user.checkins.values("beer__style__name")
        .annotate(count=Count("id"), avg=Avg("rating"))
        .order_by("-count")[:10]
    )

    # Challenges
    challenges = Challenge.objects.all()
    challenge_progress = []
    for c in challenges:
        current, required = c.progress_for(target.user)
        challenge_progress.append(
            {
                "challenge": c,
                "current": current,
                "required": required,
                "percent": int((current / required) * 100) if required else 0,
                "completed": current >= required,
            }
        )

    total_styles = BeerStyle.objects.count()
    styles_tried = target.unique_styles
    passport_percent = int((styles_tried / total_styles) * 100) if total_styles else 0

    return render(
        request,
        "beers/profile.html",
        {
            "profile": target,
            "checkins": checkins,
            "style_breakdown": style_breakdown,
            "challenges": challenge_progress,
            "styles_tried": styles_tried,
            "total_styles": total_styles,
            "passport_percent": passport_percent,
        },
    )


def register(request):
    """User registration."""
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
