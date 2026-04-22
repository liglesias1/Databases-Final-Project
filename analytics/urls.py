from django.urls import path
from . import views

app_name = "analytics"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("demand/", views.demand_trends, name="demand_trends"),
    path("regional/", views.regional_analysis, name="regional"),
    path("styles/", views.style_analysis, name="styles"),
    path("projections/", views.projections, name="projections"),
    # JSON data endpoints for Chart.js
    path("api/demand-data/", views.demand_data_api, name="demand_data_api"),
    path("api/regional-data/", views.regional_data_api, name="regional_data_api"),
    path("api/style-data/", views.style_data_api, name="style_data_api"),
]
