from django.contrib import admin
from .models import BeerStyle, Brewery, Beer, UserProfile, CheckIn, Challenge, Follow, Badge, UserBadge


@admin.register(BeerStyle)
class BeerStyleAdmin(admin.ModelAdmin):
    list_display = ("name", "family", "style_key")
    search_fields = ("name", "family")


@admin.register(Brewery)
class BreweryAdmin(admin.ModelAdmin):
    list_display = ("name", "country", "city")
    search_fields = ("name", "country", "city")


@admin.register(Beer)
class BeerAdmin(admin.ModelAdmin):
    list_display = ("name", "style", "brewery", "abv", "avg_rating")
    list_filter = ("style",)
    search_fields = ("name", "brewery__name", "style__name")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "favorite_style")


@admin.register(CheckIn)
class CheckInAdmin(admin.ModelAdmin):
    list_display = ("user", "beer", "rating", "quantity", "created_at")
    list_filter = ("rating",)


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ("name", "required_count", "required_style")


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ("follower", "followed", "created_at")


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ("icon", "name", "badge_type", "threshold")
    list_filter = ("badge_type",)


@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display = ("user", "badge", "earned_at")
