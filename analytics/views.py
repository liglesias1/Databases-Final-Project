import json
from django.shortcuts import render
from django.http import JsonResponse
from .decorators import manufacturer_required
from .models import DemandSnapshot
from . import services


@manufacturer_required()
def dashboard(request):
    ctx = services.get_dashboard_data(request.manufacturer)
    ctx["active_page"] = "dashboard"
    return render(request, "analytics/dashboard.html", ctx)


@manufacturer_required(roles=["admin", "supply_chain", "sales"])
def demand_trends(request):
    granularity = request.GET.get("granularity", "week")
    style_id = request.GET.get("style_id")
    ctx = services.get_demand_trends_data(request.manufacturer, granularity, style_id)
    ctx["active_page"] = "demand"
    return render(request, "analytics/demand_trends.html", ctx)


@manufacturer_required(roles=["admin", "supply_chain", "sales"])
def regional_analysis(request):
    ctx = services.get_regional_data(request.manufacturer)
    ctx["active_page"] = "regional"
    return render(request, "analytics/regional.html", ctx)


@manufacturer_required(roles=["admin", "supply_chain", "sales"])
def style_analysis(request):
    ctx = services.get_style_data(request.manufacturer)
    ctx["active_page"] = "styles"
    return render(request, "analytics/styles.html", ctx)


@manufacturer_required()
def projections(request):
    granularity = request.GET.get("granularity", "week")
    ctx = services.get_projection_data(request.manufacturer, granularity)
    ctx["active_page"] = "projections"
    return render(request, "analytics/projections.html", ctx)


# --- JSON API endpoints for Chart.js AJAX updates ---


@manufacturer_required(roles=["admin", "supply_chain", "sales"])
def demand_data_api(request):
    granularity = request.GET.get("granularity", "week")
    style_id = request.GET.get("style_id")
    data = services.get_demand_trends_data(request.manufacturer, granularity, style_id)
    return JsonResponse(data["chart_data"])


@manufacturer_required(roles=["admin", "supply_chain", "sales"])
def regional_data_api(request):
    data = services.get_regional_data(request.manufacturer)
    return JsonResponse(data["chart_data"])


@manufacturer_required(roles=["admin", "supply_chain", "sales"])
def style_data_api(request):
    data = services.get_style_data(request.manufacturer)
    return JsonResponse(data["chart_data"])
