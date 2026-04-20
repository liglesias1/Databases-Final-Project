"""
Enrich brewery data with correct countries and coordinates.

Strategy:
1. Name heuristics to detect country from brewery name (fast, no API)
2. OpenBreweryDB API search for US breweries (best coverage)
3. Country centroid coordinates as fallback

Usage:
    python manage.py enrich_breweries
    python manage.py enrich_breweries --api       # also query OpenBreweryDB
    python manage.py enrich_breweries --limit 50  # test with first 50
"""

import time
import requests
from django.core.management.base import BaseCommand
from django.db import transaction
from beers.models import Brewery


# Country centroid coordinates (lat, lng)
COUNTRY_COORDS = {
    "United States": (39.8283, -98.5795),
    "Germany": (51.1657, 10.4515),
    "Belgium": (50.8503, 4.3517),
    "United Kingdom": (55.3781, -3.4360),
    "Ireland": (53.1424, -7.6921),
    "Czech Republic": (49.8175, 15.4730),
    "Netherlands": (52.1326, 5.2913),
    "Japan": (36.2048, 138.2529),
    "Mexico": (23.6345, -102.5528),
    "Canada": (56.1304, -106.3468),
    "Australia": (-25.2744, 133.7751),
    "Denmark": (56.2639, 9.5018),
    "France": (46.2276, 2.2137),
    "Italy": (41.8719, 12.5674),
    "Spain": (40.4637, -3.7492),
    "Brazil": (-14.2350, -51.9253),
    "Austria": (47.5162, 14.5501),
    "Poland": (51.9194, 19.1451),
    "Norway": (60.4720, 8.4689),
    "Sweden": (60.1282, 18.6435),
    "Switzerland": (46.8182, 8.2275),
    "Scotland": (56.4907, -4.2026),
    "New Zealand": (-40.9006, 174.8860),
    "China": (35.8617, 104.1954),
    "South Korea": (35.9078, 127.7669),
    "Thailand": (15.8700, 100.9925),
    "Vietnam": (14.0583, 108.2772),
    "India": (20.5937, 78.9629),
    "Russia": (61.5240, 105.3188),
    "Lithuania": (55.1694, 23.8813),
    "Latvia": (56.8796, 24.6032),
    "Estonia": (58.5953, 25.0136),
    "Finland": (61.9241, 25.7482),
    "Iceland": (64.9631, -19.0208),
    "Portugal": (39.3999, -8.2245),
    "South Africa": (-30.5595, 22.9375),
    "Argentina": (-38.4161, -63.6167),
    "Colombia": (4.5709, -74.2973),
    "Peru": (-9.1900, -75.0152),
    "Philippines": (12.8797, 121.7740),
    "Turkey": (38.9637, 35.2433),
    "Israel": (31.0461, 34.8516),
}

# Name patterns that indicate country of origin
NAME_HEURISTICS = [
    # German patterns
    (["Brauerei", "Brauhaus", "Hofbrau", "Weihenstephan", "Erdinger", "Paulaner",
      "Spaten", "Augustiner", "Hacker-Pschorr", "Lowenbrau", "Bitburger", "Warsteiner",
      "Krombacher", "Veltins", "Radeberger", "Kolsch", "Aktien", "Ayinger", "Andechs",
      "Jever", "Flensburger", "Rothaus", "Schlenkerla", "Schneider"], "Germany"),

    # Belgian patterns
    (["Abbaye", "Abdij", "Trappist", "Chimay", "Westmalle", "Westvleteren", "Orval",
      "Rochefort", "Achel", "Duvel", "Leffe", "Hoegaarden", "Delirium", "Cantillon",
      "Lambic", "Brasserie", "Brouwerij", "Lindemans", "Rodenbach", "Huyghe",
      "St. Bernardus", "Val-Dieu", "Boon", "Mort Subite"], "Belgium"),

    # British patterns
    (["Fuller", "Samuel Smith", "Adnams", "Greene King", "Marston", "Theakston",
      "Young's", "Timothy Taylor", "Thornbridge", "BrewDog", "Meantime", "Camden",
      "Beavertown", "Kernel", "Cloudwater", "Harbour", "Magic Rock", "Buxton",
      "Siren", "Wild Beer"], "United Kingdom"),

    # Irish patterns
    (["Guinness", "Smithwick", "Beamish", "Murphy", "Franciscan", "O'Hara",
      "Galway", "Porterhouse", "Eight Degrees", "Whiplash"], "Ireland"),

    # Czech patterns
    (["Pilsner Urquell", "Budweiser Budvar", "Staropramen", "Kozel", "Gambrinus",
      "Bernard", "Krusovice", "Radegast", "Svijany", "Pivovar"], "Czech Republic"),

    # Dutch patterns
    (["Heineken", "Grolsch", "Bavaria", "Amstel", "Brand", "La Trappe",
      "Texels", "Jopen", "Brouwerij 't IJ", "De Molen"], "Netherlands"),

    # Danish patterns
    (["Carlsberg", "Tuborg", "Mikkeller", "To Ol", "Amager"], "Denmark"),

    # Japanese patterns
    (["Sapporo", "Asahi", "Kirin", "Suntory", "Hitachino", "Coedo",
      "Baird", "Shiga Kogen", "Minoh"], "Japan"),

    # Mexican patterns
    (["Cerveceria", "Grupo Modelo", "Corona", "Dos Equis", "Tecate",
      "Bohemia", "Pacifico", "Victoria"], "Mexico"),

    # Canadian patterns
    (["Molson", "Labatt", "Moosehead", "Alexander Keith", "Unibroue",
      "Dieu du Ciel", "Beau's", "Great Lakes Brewery"], "Canada"),

    # Australian patterns
    (["Foster", "Coopers", "Carlton", "James Squire", "Little Creatures",
      "Stone & Wood", "Feral", "Mountain Goat", "Colonial"], "Australia"),

    # Norwegian patterns
    (["Nogne O", "Haandbryggeriet", "Lervig", "Aegir"], "Norway"),

    # Swedish patterns
    (["Omnipollo", "Dugges", "Oppigards", "Nynashamn"], "Sweden"),

    # Italian patterns
    (["Birrificio", "Baladin", "Birra del Borgo", "Brewfist", "Toccalmatto"], "Italy"),

    # French patterns
    (["Brasserie de", "Kronenbourg", "Jenlain", "Saint Omer"], "France"),

    # Lithuanian / Baltic
    (["Kalnapilis", "Svyturys", "Utenos"], "Lithuania"),
    (["Aldaris", "Lacplesis"], "Latvia"),

    # Polish
    (["Zywiec", "Tyskie", "Lech", "Okocim", "Browar"], "Poland"),

    # Swiss
    (["Feldschlosschen", "Cardinal", "Brasserie des Franches"], "Switzerland"),
]

# Known US brewery keywords (high confidence)
US_KEYWORDS = [
    "Brewing Co.", "Brewing Company", "Beer Co.", "Beer Company",
    "Brewery", "Ales", "Craft", "IPA",
    # Known US brands
    "Sierra Nevada", "Anchor", "Dogfish", "Stone Brewing", "Founders",
    "Bell's", "Lagunitas", "Deschutes", "Firestone", "Oskar Blues",
    "New Belgium", "Brooklyn", "Cigar City", "Ballast Point", "Victory",
    "Troegs", "Allagash", "Maine Beer", "Hill Farmstead", "Russian River",
    "Three Floyds", "Surly", "Odell", "Left Hand", "Avery", "Great Divide",
    "Rogue", "Widmer", "Redhook", "Boulevard", "Goose Island", "Revolution",
    "Half Acre", "Pipeworks", "Evil Twin", "Stillwater", "Westbrook",
    "Prairie", "Jester King", "Real Ale", "Karbach", "Saint Arnold",
    "Abita", "Sweetwater", "Terrapin", "Wicked Weed", "NoDa",
    "Tired Hands", "Other Half", "Grimm", "Finback", "KCBC",
    "Alaskan", "Pelican", "Elysian", "Georgetown", "Fremont",
    "Modern Times", "Pizza Port", "AleSmith", "Societe", "Green Flash",
    "Port Brewing", "Lost Abbey", "Alpine Beer", "Coronado",
    "New Glarus", "Toppling Goliath", "Perennial", "Side Project",
    "Central Waters", "Schlafly", "4 Hands", "Urban Chestnut",
    "Sun King", "Upland", "3 Floyds", "18th Street",
    "Tree House", "Trillium", "Night Shift", "Jack's Abby",
    "Lawson's", "Heady Topper", "Frost Beer", "Zero Gravity",
    "Captain Lawrence", "Singlecut", "Barrier", "Sand City",
]


def detect_country(name):
    """Try to detect country from brewery name using heuristics."""
    name_lower = name.lower()

    # Check specific country patterns
    for keywords, country in NAME_HEURISTICS:
        for kw in keywords:
            if kw.lower() in name_lower:
                return country

    # Check if likely US
    for kw in US_KEYWORDS:
        if kw.lower() in name_lower:
            return "United States"

    return None


def add_jitter(lat, lng, scale=2.0):
    """Add random jitter to coordinates so breweries in same country don't stack."""
    import random
    return (
        lat + random.uniform(-scale, scale),
        lng + random.uniform(-scale, scale),
    )


class Command(BaseCommand):
    help = "Enrich brewery data with correct countries and coordinates"

    def add_arguments(self, parser):
        parser.add_argument("--api", action="store_true", help="Query OpenBreweryDB API")
        parser.add_argument("--limit", type=int, default=None)

    @transaction.atomic
    def handle(self, *args, **options):
        use_api = options["api"]
        limit = options["limit"]

        breweries = Brewery.objects.all()
        if limit:
            breweries = breweries[:limit]

        total = breweries.count()
        heuristic_matched = 0
        api_matched = 0
        centroid_fallback = 0

        self.stdout.write(f"Enriching {total} breweries...")
        if use_api:
            self.stdout.write("  (OpenBreweryDB API enabled)")

        for i, brewery in enumerate(breweries):
            # Step 1: Try heuristic country detection
            detected = detect_country(brewery.name)

            if detected:
                brewery.country = detected
                heuristic_matched += 1
            # If no heuristic match and API enabled, try API
            elif use_api:
                coords = self._query_api(brewery.name)
                if coords:
                    brewery.country = coords["country"]
                    brewery.city = coords.get("city", "")
                    brewery.latitude = coords["lat"]
                    brewery.longitude = coords["lng"]
                    brewery.save()
                    api_matched += 1
                    if (i + 1) % 50 == 0:
                        self.stdout.write(f"  processed {i + 1}/{total}...")
                    continue

            # Step 2: Assign coordinates from country centroid (with jitter)
            country = brewery.country
            if country in COUNTRY_COORDS:
                lat, lng = COUNTRY_COORDS[country]
                lat, lng = add_jitter(lat, lng, scale=1.5)
                brewery.latitude = round(lat, 4)
                brewery.longitude = round(lng, 4)
                centroid_fallback += 1
            else:
                # Unknown country, default to center of US with wide jitter
                lat, lng = add_jitter(39.8, -98.6, scale=5.0)
                brewery.latitude = round(lat, 4)
                brewery.longitude = round(lng, 4)
                if not brewery.country:
                    brewery.country = "Unknown"
                centroid_fallback += 1

            brewery.save()

            if (i + 1) % 100 == 0:
                self.stdout.write(f"  processed {i + 1}/{total}...")

        # Report
        with_coords = Brewery.objects.exclude(latitude=None).count()
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Done. {total} breweries processed."))
        self.stdout.write(f"  Heuristic country match: {heuristic_matched}")
        self.stdout.write(f"  API match:               {api_matched}")
        self.stdout.write(f"  Centroid fallback:       {centroid_fallback}")
        self.stdout.write(f"  With coordinates:        {with_coords}/{total}")

        # Country distribution
        from django.db.models import Count
        self.stdout.write("")
        self.stdout.write("Country distribution:")
        for c in (Brewery.objects.values("country")
                  .annotate(n=Count("id")).order_by("-n")[:15]):
            self.stdout.write(f"  {c['country']:25s}: {c['n']}")

    def _query_api(self, name):
        """Search OpenBreweryDB for a brewery by name."""
        try:
            query = name.replace("'", "").replace("&", "and")[:50]
            resp = requests.get(
                "https://api.openbrewerydb.org/v1/breweries/search",
                params={"query": query, "per_page": 1},
                timeout=5,
            )
            if resp.status_code == 200:
                results = resp.json()
                if results:
                    r = results[0]
                    lat = r.get("latitude")
                    lng = r.get("longitude")
                    if lat and lng:
                        return {
                            "country": r.get("country", "United States"),
                            "city": r.get("city", ""),
                            "lat": float(lat),
                            "lng": float(lng),
                        }
            time.sleep(0.2)  # rate limit
        except Exception:
            pass
        return None
