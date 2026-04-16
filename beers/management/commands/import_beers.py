"""
Import beers from CSV datasets.

Usage:
    python manage.py import_beers
    python manage.py import_beers --limit 500    # faster for testing
    python manage.py import_beers --fresh        # wipe and reimport
"""

import csv
from pathlib import Path
from django.core.management.base import BaseCommand
from django.db import transaction
from beers.models import Beer, BeerStyle, Brewery, Challenge


# Map style names to their family (Ale, Lager, Stout, etc.)
STYLE_FAMILIES = {
    "ale": "Ale",
    "ipa": "Ale",
    "pale ale": "Ale",
    "bitter": "Ale",
    "brown": "Ale",
    "porter": "Stout & Porter",
    "stout": "Stout & Porter",
    "lager": "Lager",
    "pilsner": "Lager",
    "pils": "Lager",
    "bock": "Lager",
    "wheat": "Wheat",
    "witbier": "Wheat",
    "weissbier": "Wheat",
    "hefeweizen": "Wheat",
    "saison": "Farmhouse",
    "farmhouse": "Farmhouse",
    "sour": "Sour & Wild",
    "lambic": "Sour & Wild",
    "gueuze": "Sour & Wild",
    "berliner": "Sour & Wild",
    "gose": "Sour & Wild",
    "tripel": "Belgian Strong",
    "dubbel": "Belgian Strong",
    "quadrupel": "Belgian Strong",
    "quad": "Belgian Strong",
    "belgian": "Belgian Strong",
    "barleywine": "Strong Ale",
    "strong": "Strong Ale",
    "altbier": "Ale",
    "kolsch": "Ale",
    "cream": "Ale",
    "scottish": "Ale",
    "mild": "Ale",
    "rye": "Ale",
    "smoked": "Specialty",
    "fruit": "Specialty",
    "herbed": "Specialty",
    "spiced": "Specialty",
    "pumpkin": "Specialty",
    "cider": "Specialty",
    "mead": "Specialty",
    "rauchbier": "Specialty",
    "marzen": "Lager",
    "oktoberfest": "Lager",
    "schwarzbier": "Lager",
    "dunkel": "Lager",
    "helles": "Lager",
    "vienna": "Lager",
    "american adjunct": "Lager",
}


def detect_family(style_name):
    lower = style_name.lower()
    for key, family in STYLE_FAMILIES.items():
        if key in lower:
            return family
    return "Other"


def parse_int(value, default=0):
    if value is None or value == "":
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def parse_float(value, default=None):
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


class Command(BaseCommand):
    help = "Import beer data from CSV files"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Limit rows imported (for quick tests)",
        )
        parser.add_argument(
            "--fresh",
            action="store_true",
            help="Delete existing beers/breweries/styles before import",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        limit = options["limit"]
        fresh = options["fresh"]

        csv_path = (
            Path(__file__).resolve().parent.parent.parent / "beer_profile_and_ratings.csv"
        )
        if not csv_path.exists():
            self.stderr.write(f"CSV not found at {csv_path}")
            return

        if fresh:
            self.stdout.write("Wiping existing data...")
            Beer.objects.all().delete()
            Brewery.objects.all().delete()
            BeerStyle.objects.all().delete()

        styles_cache = {s.name: s for s in BeerStyle.objects.all()}
        breweries_cache = {b.name: b for b in Brewery.objects.all()}

        imported = 0
        skipped = 0

        with open(csv_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if limit and imported >= limit:
                    break

                name = (row.get("Name") or "").strip()
                style_name = (row.get("Style") or "").strip()
                brewery_name = (row.get("Brewery") or "").strip()

                if not name or not style_name or not brewery_name:
                    skipped += 1
                    continue

                # Get or create style
                if style_name not in styles_cache:
                    style = BeerStyle.objects.create(
                        name=style_name,
                        family=detect_family(style_name),
                    )
                    styles_cache[style_name] = style
                style = styles_cache[style_name]

                # Get or create brewery
                if brewery_name not in breweries_cache:
                    brewery = Brewery.objects.create(name=brewery_name)
                    breweries_cache[brewery_name] = brewery
                brewery = breweries_cache[brewery_name]

                # Skip if exact duplicate beer exists
                if Beer.objects.filter(
                    name=name, brewery=brewery, style=style
                ).exists():
                    skipped += 1
                    continue

                Beer.objects.create(
                    name=name,
                    style=style,
                    brewery=brewery,
                    description=(row.get("Description") or "").strip()[:2000],
                    abv=parse_float(row.get("ABV")),
                    min_ibu=parse_int(row.get("Min IBU"), None),
                    max_ibu=parse_int(row.get("Max IBU"), None),
                    avg_rating=parse_float(row.get("review_overall") or row.get("Ave Rating")),
                    astringency=parse_int(row.get("Astringency")),
                    body=parse_int(row.get("Body")),
                    alcohol=parse_int(row.get("Alcohol")),
                    bitter=parse_int(row.get("Bitter")),
                    sweet=parse_int(row.get("Sweet")),
                    sour=parse_int(row.get("Sour")),
                    salty=parse_int(row.get("Salty")),
                    fruits=parse_int(row.get("Fruits")),
                    hoppy=parse_int(row.get("Hoppy")),
                    spices=parse_int(row.get("Spices")),
                    malty=parse_int(row.get("Malty")),
                )
                imported += 1

                if imported % 500 == 0:
                    self.stdout.write(f"  imported {imported}...")

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Imported {imported} beers ({skipped} skipped). "
                f"{BeerStyle.objects.count()} styles, "
                f"{Brewery.objects.count()} breweries."
            )
        )

        # Seed some default challenges
        self._seed_challenges()

    def _seed_challenges(self):
        if Challenge.objects.exists():
            return
        self.stdout.write("Seeding default challenges...")
        Challenge.objects.create(
            name="Getting Started",
            description="Log your first 5 beers.",
            required_count=5,
            icon="🍺",
        )
        Challenge.objects.create(
            name="Hop Head",
            description="Try 5 different IPAs.",
            required_count=5,
            required_style=BeerStyle.objects.filter(name__icontains="IPA").first(),
            icon="🌿",
        )
        stout = BeerStyle.objects.filter(name__icontains="stout").first()
        if stout:
            Challenge.objects.create(
                name="Dark Side",
                description="Try 5 stouts.",
                required_count=5,
                required_style=stout,
                icon="🖤",
            )
        Challenge.objects.create(
            name="Globetrotter",
            description="Try 20 different beers.",
            required_count=20,
            icon="🌍",
        )
        Challenge.objects.create(
            name="Connoisseur",
            description="Try 50 different beers.",
            required_count=50,
            icon="🏆",
        )
