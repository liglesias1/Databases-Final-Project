from datetime import timedelta
from django.db.models import Count, Sum, Avg, Q
from django.db.models.functions import TruncWeek, TruncMonth

from beers.models import CheckIn, BeerStyle, Beer
from .models import DemandSnapshot


# ---------------------------------------------------------------------------
# Snapshot builder
# ---------------------------------------------------------------------------

def rebuild_snapshots():
    """Truncate and rebuild all DemandSnapshot rows from CheckIn data."""
    DemandSnapshot.objects.all().delete()
    rows = []

    for granularity, trunc_fn in [("week", TruncWeek), ("month", TruncMonth)]:
        # --- Market-wide aggregates ---
        qs = (
            CheckIn.objects
            .annotate(period=trunc_fn("created_at"))
            .values("period")
            .annotate(
                checkin_count=Count("id"),
                quantity_total=Sum("quantity"),
                unique_users=Count("user", distinct=True),
                avg_rating=Avg("rating"),
            )
            .order_by("period")
        )
        for row in qs:
            rows.append(DemandSnapshot(
                period_start=row["period"].date() if hasattr(row["period"], "date") else row["period"],
                granularity=granularity,
                checkin_count=row["checkin_count"],
                quantity_total=row["quantity_total"] or 0,
                unique_users=row["unique_users"],
                avg_rating=row["avg_rating"],
            ))

        # --- By style ---
        qs_style = (
            CheckIn.objects
            .annotate(period=trunc_fn("created_at"))
            .values("period", "beer__style")
            .annotate(
                checkin_count=Count("id"),
                quantity_total=Sum("quantity"),
                unique_users=Count("user", distinct=True),
                avg_rating=Avg("rating"),
            )
            .order_by("period")
        )
        for row in qs_style:
            rows.append(DemandSnapshot(
                period_start=row["period"].date() if hasattr(row["period"], "date") else row["period"],
                granularity=granularity,
                style_id=row["beer__style"],
                checkin_count=row["checkin_count"],
                quantity_total=row["quantity_total"] or 0,
                unique_users=row["unique_users"],
                avg_rating=row["avg_rating"],
            ))

        # --- By country ---
        qs_country = (
            CheckIn.objects
            .exclude(beer__brewery__country="")
            .annotate(period=trunc_fn("created_at"))
            .values("period", "beer__brewery__country")
            .annotate(
                checkin_count=Count("id"),
                quantity_total=Sum("quantity"),
                unique_users=Count("user", distinct=True),
                avg_rating=Avg("rating"),
            )
            .order_by("period")
        )
        for row in qs_country:
            rows.append(DemandSnapshot(
                period_start=row["period"].date() if hasattr(row["period"], "date") else row["period"],
                granularity=granularity,
                country=row["beer__brewery__country"],
                checkin_count=row["checkin_count"],
                quantity_total=row["quantity_total"] or 0,
                unique_users=row["unique_users"],
                avg_rating=row["avg_rating"],
            ))

        # --- By brewery ---
        qs_brewery = (
            CheckIn.objects
            .annotate(period=trunc_fn("created_at"))
            .values("period", "beer__brewery")
            .annotate(
                checkin_count=Count("id"),
                quantity_total=Sum("quantity"),
                unique_users=Count("user", distinct=True),
                avg_rating=Avg("rating"),
            )
            .order_by("period")
        )
        for row in qs_brewery:
            rows.append(DemandSnapshot(
                period_start=row["period"].date() if hasattr(row["period"], "date") else row["period"],
                granularity=granularity,
                brewery_id=row["beer__brewery"],
                checkin_count=row["checkin_count"],
                quantity_total=row["quantity_total"] or 0,
                unique_users=row["unique_users"],
                avg_rating=row["avg_rating"],
            ))

    DemandSnapshot.objects.bulk_create(rows)
    return len(rows)


# ---------------------------------------------------------------------------
# Projection helpers
# ---------------------------------------------------------------------------

def compute_moving_average(values, window=4):
    """Simple moving average over the last `window` periods."""
    ma = []
    for i in range(len(values)):
        if i < window - 1:
            ma.append(None)
        else:
            ma.append(round(sum(values[i - window + 1 : i + 1]) / window, 1))
    return ma


def compute_trend_line(values):
    """Linear regression. Returns (slope, intercept)."""
    n = len(values)
    if n < 2:
        return 0, (values[0] if values else 0)
    x_mean = (n - 1) / 2
    y_mean = sum(values) / n
    numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    slope = numerator / denominator if denominator else 0
    intercept = y_mean - slope * x_mean
    return slope, intercept


def project_forward(values, periods_ahead=4):
    """Project demand forward using trend line."""
    slope, intercept = compute_trend_line(values)
    n = len(values)
    return [max(0, round(slope * (n + i) + intercept, 1)) for i in range(periods_ahead)]


# ---------------------------------------------------------------------------
# Scoping helper
# ---------------------------------------------------------------------------

def _scope_snapshots(manufacturer, granularity="week"):
    """Return a base queryset scoped to the manufacturer's breweries (or all)."""
    brewery_ids = list(manufacturer.breweries.values_list("id", flat=True))
    qs = DemandSnapshot.objects.filter(granularity=granularity)
    if brewery_ids:
        qs = qs.filter(Q(brewery__isnull=True) | Q(brewery_id__in=brewery_ids))
    return qs


# ---------------------------------------------------------------------------
# Dashboard data (executive overview)
# ---------------------------------------------------------------------------

def get_dashboard_data(manufacturer):
    """KPIs, sparkline, and trending styles for the executive dashboard."""
    qs = _scope_snapshots(manufacturer, "week")

    # Market-wide weekly snapshots (no dimension filters)
    market = (
        qs.filter(style__isnull=True, country="", brewery__isnull=True)
        .order_by("period_start")
    )
    market_list = list(market)

    # KPIs
    current = market_list[-1] if market_list else None
    previous = market_list[-2] if len(market_list) >= 2 else None

    def delta_pct(curr_val, prev_val):
        if not prev_val or not curr_val:
            return 0
        return round((curr_val - prev_val) / prev_val * 100, 1) if prev_val else 0

    kpis = {
        "demand": current.quantity_total if current else 0,
        "demand_delta": delta_pct(
            current.quantity_total if current else 0,
            previous.quantity_total if previous else 0,
        ),
        "consumers": current.unique_users if current else 0,
        "consumers_delta": delta_pct(
            current.unique_users if current else 0,
            previous.unique_users if previous else 0,
        ),
        "avg_rating": round(current.avg_rating, 2) if current and current.avg_rating else 0,
        "checkins": current.checkin_count if current else 0,
    }

    # Sparkline (last 8 weeks)
    sparkline = [s.quantity_total for s in market_list[-8:]]

    # Trending styles (biggest WoW growth)
    style_snapshots = (
        qs.filter(country="", brewery__isnull=True, style__isnull=False)
        .select_related("style")
        .order_by("style", "period_start")
    )
    style_data = {}
    for s in style_snapshots:
        style_data.setdefault(s.style_id, []).append(s)

    trending = []
    for style_id, snaps in style_data.items():
        if len(snaps) >= 2:
            curr = snaps[-1].quantity_total
            prev = snaps[-2].quantity_total
            growth = curr - prev
            trending.append({
                "name": snaps[-1].style.name,
                "current": curr,
                "previous": prev,
                "growth": growth,
                "growth_pct": delta_pct(curr, prev),
            })
    trending.sort(key=lambda x: x["growth"], reverse=True)

    import json
    return {
        "kpis": kpis,
        "sparkline_data": json.dumps(sparkline),
        "trending_styles": trending[:5],
    }


# ---------------------------------------------------------------------------
# Demand trends
# ---------------------------------------------------------------------------

def get_demand_trends_data(manufacturer, granularity="week", style_id=None):
    """Time-series demand data for charts."""
    qs = _scope_snapshots(manufacturer, granularity)

    if style_id:
        qs = qs.filter(style_id=style_id, country="", brewery__isnull=True)
    else:
        qs = qs.filter(style__isnull=True, country="", brewery__isnull=True)

    snapshots = list(qs.order_by("period_start"))
    labels = [s.period_start.strftime("%b %d") for s in snapshots]
    values = [s.quantity_total for s in snapshots]
    ma = compute_moving_average(values)

    # Style breakdown (stacked area data)
    style_breakdown = {}
    if not style_id:
        style_qs = (
            _scope_snapshots(manufacturer, granularity)
            .filter(style__isnull=False, country="", brewery__isnull=True)
            .select_related("style")
            .order_by("period_start")
        )
        for s in style_qs:
            name = s.style.family or s.style.name
            style_breakdown.setdefault(name, {})
            key = s.period_start.strftime("%b %d")
            style_breakdown[name][key] = (
                style_breakdown[name].get(key, 0) + s.quantity_total
            )

    # Available styles for filter
    styles = list(
        BeerStyle.objects.filter(
            beers__checkins__isnull=False
        ).distinct().values("id", "name").order_by("name")
    )

    chart_data = {
        "labels": labels,
        "values": values,
        "moving_avg": ma,
        "style_breakdown": style_breakdown,
    }

    return {
        "chart_data": chart_data,
        "chart_data_json": _to_json(chart_data),
        "styles": styles,
        "selected_style": style_id,
        "granularity": granularity,
    }


# ---------------------------------------------------------------------------
# Regional
# ---------------------------------------------------------------------------

def get_regional_data(manufacturer):
    """Geographic demand data."""
    qs = _scope_snapshots(manufacturer, "month")

    country_qs = (
        qs.filter(style__isnull=True, brewery__isnull=True)
        .exclude(country="")
        .order_by("country", "-period_start")
    )
    seen = set()
    countries = []
    for s in country_qs:
        if s.country not in seen:
            seen.add(s.country)
            countries.append({
                "country": s.country,
                "checkins": s.checkin_count,
                "quantity": s.quantity_total,
                "users": s.unique_users,
            })
    countries.sort(key=lambda x: x["quantity"], reverse=True)

    chart_data = {
        "labels": [c["country"] for c in countries[:15]],
        "values": [c["quantity"] for c in countries[:15]],
    }

    # Heatmap data from checkins directly
    from beers.views import _build_heatmap_data
    brewery_ids = list(manufacturer.breweries.values_list("id", flat=True))
    checkin_qs = CheckIn.objects.all()
    if brewery_ids:
        checkin_qs = checkin_qs.filter(beer__brewery_id__in=brewery_ids)
    heatmap = _build_heatmap_data(checkin_qs)

    return {
        "countries": countries,
        "chart_data": chart_data,
        "chart_data_json": _to_json(chart_data),
        "heatmap_data": _to_json(heatmap),
    }


# ---------------------------------------------------------------------------
# Style analysis
# ---------------------------------------------------------------------------

def get_style_data(manufacturer):
    """Style ranking and flavor profile data."""
    qs = _scope_snapshots(manufacturer, "month")

    style_totals = (
        qs.filter(country="", brewery__isnull=True, style__isnull=False)
        .values("style__id", "style__name")
        .annotate(
            total_quantity=Sum("quantity_total"),
            total_checkins=Sum("checkin_count"),
            avg_rating=Avg("avg_rating"),
        )
        .order_by("-total_quantity")
    )
    style_list = list(style_totals[:20])

    # Flavor profiles for top 5 styles
    flavor_fields = [
        "bitter", "sweet", "sour", "malty", "hoppy", "fruits", "spices", "body"
    ]
    flavor_profiles = {}
    for s in style_list[:5]:
        beers = Beer.objects.filter(style_id=s["style__id"])
        profile = {}
        for f in flavor_fields:
            vals = [getattr(b, f) for b in beers if getattr(b, f, None) is not None]
            profile[f] = round(sum(vals) / len(vals), 1) if vals else 0
        flavor_profiles[s["style__name"]] = profile

    chart_data = {
        "labels": [s["style__name"] for s in style_list],
        "values": [s["total_quantity"] for s in style_list],
        "flavor_labels": flavor_fields,
        "flavor_profiles": flavor_profiles,
    }

    return {
        "styles": style_list,
        "chart_data": chart_data,
        "chart_data_json": _to_json(chart_data),
    }


# ---------------------------------------------------------------------------
# Projections
# ---------------------------------------------------------------------------

def get_projection_data(manufacturer, granularity="week"):
    """Historical data + forward projections."""
    qs = _scope_snapshots(manufacturer, granularity)
    snapshots = list(
        qs.filter(style__isnull=True, country="", brewery__isnull=True)
        .order_by("period_start")
    )

    labels = [s.period_start.strftime("%b %d") for s in snapshots]
    values = [s.quantity_total for s in snapshots]
    ma = compute_moving_average(values)

    # Forward projection
    periods_ahead = 4
    projected = project_forward(values, periods_ahead)

    # Generate future labels
    if snapshots:
        last_date = snapshots[-1].period_start
        delta = timedelta(weeks=1) if granularity == "week" else timedelta(days=30)
        future_labels = [
            (last_date + delta * (i + 1)).strftime("%b %d")
            for i in range(periods_ahead)
        ]
    else:
        future_labels = [f"+{i+1}" for i in range(periods_ahead)]

    # Per-style projections (top 10)
    style_qs = (
        _scope_snapshots(manufacturer, granularity)
        .filter(country="", brewery__isnull=True, style__isnull=False)
        .select_related("style")
        .order_by("style", "period_start")
    )
    style_data = {}
    for s in style_qs:
        style_data.setdefault(s.style_id, {"name": s.style.name, "values": []})
        style_data[s.style_id]["values"].append(s.quantity_total)

    style_projections = []
    for style_id, info in style_data.items():
        proj = project_forward(info["values"], periods_ahead)
        style_projections.append({
            "name": info["name"],
            "current": info["values"][-1] if info["values"] else 0,
            "projected": proj,
            "projected_avg": round(sum(proj) / len(proj), 1) if proj else 0,
            "trend": "up" if proj and proj[-1] > (info["values"][-1] if info["values"] else 0) else "down",
        })
    style_projections.sort(key=lambda x: x["projected_avg"], reverse=True)

    # Confidence based on data volume
    data_points = len(values)
    if data_points >= 12:
        confidence = "high"
    elif data_points >= 6:
        confidence = "medium"
    else:
        confidence = "low"

    chart_data = {
        "labels": labels,
        "values": values,
        "moving_avg": ma,
        "future_labels": future_labels,
        "projected": projected,
    }

    return {
        "chart_data": chart_data,
        "chart_data_json": _to_json(chart_data),
        "style_projections": style_projections[:10],
        "confidence": confidence,
        "granularity": granularity,
    }


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _to_json(data):
    import json
    return json.dumps(data)
