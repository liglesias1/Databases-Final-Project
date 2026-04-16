# BeerPass

Goodreads for beer. Django MVP for a databases group project.

## What it does

- Browse a catalog of 3,000+ beers with flavor profiles, ABV, IBU, and ratings.
- Search and filter by style, ABV, brewery.
- Register, log in, and check in beers you've tried with a rating and notes.
- Track your "beer passport" — how many styles you've explored.
- Compete on leaderboards (most beers tried, most styles explored, most countries covered).
- Complete challenges ("Try 5 IPAs", "Try 50 different beers").
- View detailed flavor profiles per beer.

## Stack

- Django 4.2 (MVC)
- SQLite (dev) — can be swapped for Postgres
- Bootstrap 5 (frontend)
- Beer data from the `liglesias1/Databases-Final-Project` dataset

## Quick start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run migrations
python manage.py migrate

# 3. Import beers (takes ~30 seconds)
python manage.py import_beers

# 4. Create a superuser (optional, for /admin)
python manage.py createsuperuser

# 5. Run the server
python manage.py runserver
```

Visit http://localhost:8000

## Team split (5 people)

| Owner | Responsibility |
|---|---|
| **Models / Data** | `beers/models.py`, `beers/management/commands/import_beers.py` |
| **Auth / Core Views** | `beers/views.py` (login, register, checkin, profile), `beerapp/urls.py` |
| **Frontend** | `beers/templates/` — base layout, beer list, detail, profile |
| **Features** | Leaderboard, challenges, style explorer, passport logic |
| **AI + Community** | [To be built] Claude API sommelier, community chat, brewery map |

## What's in this MVP

- ✅ All models
- ✅ Data import from CSV
- ✅ Auth (register/login/logout)
- ✅ Beer catalog + search + filters + pagination
- ✅ Beer detail page with flavor profile
- ✅ Check-in system (rating + notes)
- ✅ User profiles with passport progress
- ✅ Leaderboards (3 rankings)
- ✅ Challenges with progress tracking
- ✅ Style explorer grouped by family
- ✅ Dark craft-beer themed UI

## What's next (Phase 2)

- AI sommelier (Claude API): "I like Guinness, what should I try?"
- Community chat (Django Channels or HTTP polling)
- Brewery world map (Leaflet.js + OpenBreweryDB)
- Beer style family tree (D3.js)
- Radar chart flavor profiles on profile page

## Presentation tips

1. **Open with the elevator pitch**: "Goodreads, but for beer."
2. **Live demo flow**: filter catalog → check in a beer → show leaderboard update → show profile/passport.
3. **Backup**: record the demo in advance in case live demo fails.
