from django.urls import path
from . import views

urlpatterns = [
    path("", views.beer_list, name="beer_list"),
    path("beer/<int:pk>/", views.beer_detail, name="beer_detail"),
    path("beer/<int:beer_id>/checkin/", views.checkin, name="checkin"),
    path("leaderboard/", views.leaderboard, name="leaderboard"),
    path("styles/", views.style_list, name="style_list"),
    path("styles/<int:pk>/", views.style_detail, name="style_detail"),
    path("profile/", views.profile, name="profile"),
    path("profile/<str:username>/", views.profile, name="user_profile"),
    path("register/", views.register, name="register"),
]
