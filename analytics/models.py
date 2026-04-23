from django.db import models
from django.contrib.auth.models import User


class Manufacturer(models.Model):
    name = models.CharField(max_length=200)
    breweries = models.ManyToManyField(
        "beers.Brewery", blank=True, related_name="manufacturers"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class ManufacturerMembership(models.Model):
    ROLE_CHOICES = [
        ("admin", "Account Admin"),
        ("supply_chain", "Supply Chain Manager"),
        ("sales", "Sales & Marketing"),
        ("executive", "Executive / C-Suite"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="manufacturer_memberships"
    )
    manufacturer = models.ForeignKey(
        Manufacturer, on_delete=models.CASCADE, related_name="members"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "manufacturer"],
                name="unique_manufacturer_membership",
            ),
        ]

    def __str__(self):
        return f"{self.user.username} @ {self.manufacturer.name} ({self.role})"


class DemandSnapshot(models.Model):
    GRANULARITY_CHOICES = [
        ("day", "Daily"),
        ("week", "Weekly"),
        ("month", "Monthly"),
    ]

    period_start = models.DateField()
    granularity = models.CharField(max_length=10, choices=GRANULARITY_CHOICES)

    # Dimensions (null = "all")
    style = models.ForeignKey(
        "beers.BeerStyle", null=True, blank=True, on_delete=models.CASCADE
    )
    brewery = models.ForeignKey(
        "beers.Brewery", null=True, blank=True, on_delete=models.CASCADE
    )
    country = models.CharField(max_length=100, blank=True, default="")

    # Metrics
    checkin_count = models.IntegerField(default=0)
    quantity_total = models.IntegerField(default=0)
    unique_users = models.IntegerField(default=0)
    avg_rating = models.FloatField(null=True, blank=True)

    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["granularity", "period_start"]),
            models.Index(fields=["granularity", "style", "period_start"]),
            models.Index(fields=["granularity", "country", "period_start"]),
            models.Index(fields=["granularity", "brewery", "period_start"]),
        ]

    def __str__(self):
        dims = []
        if self.style:
            dims.append(self.style.name)
        if self.country:
            dims.append(self.country)
        if self.brewery:
            dims.append(str(self.brewery))
        dim_str = " / ".join(dims) if dims else "All"
        return f"{self.granularity} {self.period_start} [{dim_str}]: {self.checkin_count} checkins"
