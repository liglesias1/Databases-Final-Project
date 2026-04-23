from django.urls import path
from . import views

urlpatterns = [
    path("", views.beer_list, name="beer_list"),
    path("beer/<int:pk>/", views.beer_detail, name="beer_detail"),
    path("beer/<int:beer_id>/checkin/", views.checkin, name="checkin"),
    path("leaderboard/", views.leaderboard, name="leaderboard"),
    path("styles/", views.style_list, name="style_list"),
    path("styles/<int:pk>/", views.style_detail, name="style_detail"),
    # Passport (replaces profile)
    path("passport/", views.passport, name="passport"),
    path("passport/<str:username>/", views.passport, name="user_passport"),
    # Social
    path("follow/<str:username>/", views.follow_user, name="follow_user"),
    path("unfollow/<str:username>/", views.unfollow_user, name="unfollow_user"),
    path("feed/", views.activity_feed, name="activity_feed"),
    path("users/", views.user_search, name="user_search"),
    # Recommendations
    path("recommendations/", views.recommendations, name="recommendations"),
    # Map
    path("map/", views.beer_map, name="beer_map"),
    path("map/data/", views.beer_map_data, name="beer_map_data"),
    # Auth
    path("register/", views.register, name="register"),
    # Backward compat
    path("profile/", views.profile, name="profile"),
    path("profile/<str:username>/", views.profile, name="user_profile"),
]
