from django.contrib import admin
from .models import BeerStyle, Brewery, Beer, UserProfile, CheckIn, Challenge, Follow, Badge, UserBadge


@admin.register(BeerStyle)
class BeerStyleAdmin(admin.ModelAdmin):
    list_display = ("name", "family", "style_key", "beer_count")
    list_filter = ("family",)
    search_fields = ("name", "family")
    ordering = ("family", "name")

    def beer_count(self, obj):
        return obj.beers.count()
    beer_count.short_description = "Beers"


@admin.register(Brewery)
class BreweryAdmin(admin.ModelAdmin):
    list_display = ("name", "country", "city", "brewery_type", "beer_count")
    list_filter = ("country", "brewery_type")
    search_fields = ("name", "country", "city")
    ordering = ("name",)

    def beer_count(self, obj):
        return obj.beers.count()
    beer_count.short_description = "Beers"


@admin.register(Beer)
class BeerAdmin(admin.ModelAdmin):
    list_display = ("name", "style", "brewery", "abv", "avg_rating", "checkin_count")
    list_filter = ("style__family", "style")
    search_fields = ("name", "brewery__name", "style__name")
    raw_id_fields = ("style", "brewery")
    ordering = ("-avg_rating",)
    list_per_page = 50

    def checkin_count(self, obj):
        return obj.checkins.count()
    checkin_count.short_description = "Check-ins"


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "favorite_style", "total_checkins", "unique_beers")
    search_fields = ("user__username",)
    raw_id_fields = ("favorite_style",)

    def total_checkins(self, obj):
        return obj.total_checkins
    total_checkins.short_description = "Check-ins"

    def unique_beers(self, obj):
        return obj.unique_beers
    unique_beers.short_description = "Unique beers"


@admin.register(CheckIn)
class CheckInAdmin(admin.ModelAdmin):
    list_display = ("user", "beer", "rating", "quantity", "created_at")
    list_filter = ("rating", "created_at")
    search_fields = ("user__username", "beer__name")
    raw_id_fields = ("user", "beer")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ("icon", "name", "required_count", "required_style")
    list_filter = ("required_style__family",)
    search_fields = ("name",)


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ("follower", "followed", "created_at")
    search_fields = ("follower__username", "followed__username")
    raw_id_fields = ("follower", "followed")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ("icon", "name", "badge_type", "threshold", "earned_count")
    list_filter = ("badge_type",)
    ordering = ("badge_type", "threshold")

    def earned_count(self, obj):
        return obj.userbadge_set.count()
    earned_count.short_description = "Times earned"


@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display = ("user", "badge", "earned_at")
    list_filter = ("badge__badge_type", "earned_at")
    search_fields = ("user__username", "badge__name")
    raw_id_fields = ("user", "badge")
    date_hierarchy = "earned_at"
    ordering = ("-earned_at",)
