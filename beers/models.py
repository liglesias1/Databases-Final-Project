from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class BeerStyle(models.Model):
    name = models.CharField(max_length=100, unique=True)
    style_key = models.IntegerField(null=True, blank=True)
    family = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

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

    # Flavor profile dimensions (0-100)
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

    def __str__(self):
        return self.user.username

    @property
    def total_checkins(self):
        return self.user.checkins.count()

    @property
    def unique_styles(self):
        return self.user.checkins.values("beer__style").distinct().count()

    @property
    def unique_countries(self):
        return (
            self.user.checkins.exclude(beer__brewery__country="")
            .values("beer__brewery__country")
            .distinct()
            .count()
        )


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
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} - {self.beer.name} ({self.rating}★)"


class Challenge(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField()
    required_count = models.IntegerField(default=1)
    required_style = models.ForeignKey(
        BeerStyle, null=True, blank=True, on_delete=models.SET_NULL
    )
    icon = models.CharField(max_length=10, default="🍺")

    def __str__(self):
        return self.name

    def progress_for(self, user):
        """Return (current_count, required_count) for a user."""
        qs = CheckIn.objects.filter(user=user)
        if self.required_style:
            qs = qs.filter(beer__style=self.required_style)
        # Count distinct beers
        current = qs.values("beer").distinct().count()
        return min(current, self.required_count), self.required_count

    def is_completed_for(self, user):
        current, required = self.progress_for(user)
        return current >= required
