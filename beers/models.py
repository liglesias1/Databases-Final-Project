from django.db import models
from django.contrib.auth.models import User
from django.db.models import Sum
from django.db.models.signals import post_save
from django.dispatch import receiver


class BeerStyle(models.Model):
    name = models.CharField(max_length=100, unique=True)
    style_key = models.IntegerField(null=True, blank=True)
    family = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["family"]),
        ]

    def __str__(self):
        return self.name


class Brewery(models.Model):
    name = models.CharField(max_length=200)
    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    brewery_type = models.CharField(max_length=50, blank=True)

    class Meta:
        verbose_name_plural = "Breweries"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["country"]),
            models.Index(fields=["city"]),
        ]

    def __str__(self):
        return self.name


class Beer(models.Model):
    name = models.CharField(max_length=200)
    key = models.IntegerField(unique=True, null=True, blank=True)
    style = models.ForeignKey(BeerStyle, on_delete=models.CASCADE, related_name="beers")
    brewery = models.ForeignKey(Brewery, on_delete=models.CASCADE, related_name="beers")
    abv = models.FloatField(null=True, blank=True)
    min_ibu = models.IntegerField(null=True, blank=True)
    max_ibu = models.IntegerField(null=True, blank=True)
    avg_rating = models.FloatField(null=True, blank=True)
    description = models.TextField(blank=True)

    astringency = models.IntegerField(default=0)
    body = models.IntegerField(default=0)
    alcohol = models.IntegerField(default=0)
    bitter = models.IntegerField(default=0)
    sweet = models.IntegerField(default=0)
    sour = models.IntegerField(default=0)
    salty = models.IntegerField(default=0)
    fruits = models.IntegerField(default=0)
    hoppy = models.IntegerField(default=0)
    spices = models.IntegerField(default=0)
    malty = models.IntegerField(default=0)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["abv"]),
            models.Index(fields=["style"]),
            models.Index(fields=["brewery"]),
            models.Index(fields=["key"]),
            models.Index(fields=["-avg_rating"]),
            models.Index(fields=["style", "-avg_rating"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.brewery.name})"

    @property
    def ibu_range(self):
        if self.min_ibu and self.max_ibu:
            return f"{self.min_ibu}-{self.max_ibu}"
        return "N/A"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    bio = models.TextField(blank=True)
    favorite_style = models.ForeignKey(
        BeerStyle, null=True, blank=True, on_delete=models.SET_NULL
    )

    class Meta:
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["favorite_style"]),
        ]

    def __str__(self):
        return self.user.username

    @property
    def total_checkins(self):
        return self.user.checkins.count()

    @property
    def total_drinks(self):
        result = self.user.checkins.aggregate(total=Sum("quantity"))
        return result["total"] or 0

    @property
    def unique_beers(self):
        return self.user.checkins.values("beer").distinct().count()

    @property
    def unique_styles(self):
        return self.user.checkins.values("beer__style").distinct().count()

    @property
    def unique_breweries(self):
        return self.user.checkins.values("beer__brewery").distinct().count()

    @property
    def unique_countries(self):
        return (
            self.user.checkins.exclude(beer__brewery__country="")
            .values("beer__brewery__country")
            .distinct()
            .count()
        )

    @property
    def current_streak(self):
        from .services import compute_current_streak as _streak
        return _streak(self.user)

    @property
    def longest_streak(self):
        from .services import compute_longest_streak as _longest
        return _longest(self.user)

    @property
    def following_count(self):
        return self.user.following.count()

    @property
    def followers_count(self):
        return self.user.followers.count()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


class CheckIn(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="checkins")
    beer = models.ForeignKey(Beer, on_delete=models.CASCADE, related_name="checkins")
    rating = models.IntegerField(
        choices=[(i, f"{i} stars") for i in range(1, 6)], default=3
    )
    quantity = models.IntegerField(default=1)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["beer"]),
            models.Index(fields=["user", "beer"]),
            models.Index(fields=["created_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(rating__gte=1, rating__lte=5),
                name="valid_rating",
            ),
            models.CheckConstraint(
                check=models.Q(quantity__gte=1),
                name="positive_quantity",
            ),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.beer.name} ({self.rating}*)"


class Challenge(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField()
    required_count = models.IntegerField(default=1)
    required_style = models.ForeignKey(
        BeerStyle, null=True, blank=True, on_delete=models.SET_NULL
    )
    icon = models.CharField(max_length=10, default="")

    class Meta:
        indexes = [
            models.Index(fields=["required_count"]),
            models.Index(fields=["required_style"]),
        ]

    def __str__(self):
        return self.name

    def progress_for(self, user):
        qs = CheckIn.objects.filter(user=user)
        if self.required_style:
            qs = qs.filter(beer__style=self.required_style)
        current = qs.values("beer").distinct().count()
        return min(current, self.required_count), self.required_count

    def is_completed_for(self, user):
        current, required = self.progress_for(user)
        return current >= required


class Follow(models.Model):
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name="following")
    followed = models.ForeignKey(User, on_delete=models.CASCADE, related_name="followers")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["follower", "followed"],
                name="unique_follow_relationship",
            ),
            models.CheckConstraint(
                check=~models.Q(follower=models.F("followed")),
                name="no_self_follow",
            ),
        ]
        indexes = [
            models.Index(fields=["follower"]),
            models.Index(fields=["followed"]),
        ]

    def __str__(self):
        return f"{self.follower.username} -> {self.followed.username}"


class Badge(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    icon = models.CharField(max_length=10, default="")
    badge_type = models.CharField(
        max_length=20,
        choices=[
            ("beers", "Beer count"),
            ("styles", "Style count"),
            ("streak", "Streak"),
            ("social", "Social"),
        ],
    )
    threshold = models.IntegerField(default=1)

    class Meta:
        ordering = ["badge_type", "threshold"]
        indexes = [
            models.Index(fields=["badge_type"]),
            models.Index(fields=["threshold"]),
            models.Index(fields=["name"]),
        ]

    def __str__(self):
        return f"{self.icon} {self.name}"

    def is_earned_by(self, user):
        from .services import compute_current_streak as _streak

        if self.badge_type == "beers":
            return user.checkins.values("beer").distinct().count() >= self.threshold
        elif self.badge_type == "styles":
            return user.checkins.values("beer__style").distinct().count() >= self.threshold
        elif self.badge_type == "streak":
            return _streak(user) >= self.threshold
        elif self.badge_type == "social":
            if "follow" in self.name.lower() or "butterfly" in self.name.lower():
                return user.following.count() >= self.threshold
            return user.followers.count() >= self.threshold
        return False


class UserBadge(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="earned_badges")
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE)
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-earned_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "badge"],
                name="unique_user_badge",
            ),
        ]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["badge"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.badge.name}"


# ============================================================
# Re-export from services.py for backward compatibility
# ============================================================
from .services import compute_current_streak, compute_longest_streak, check_and_award_badges  # noqa: E402
