from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.utils import timezone
from datetime import timedelta

from .models import (
    Beer, BeerStyle, Brewery, CheckIn, Follow,
    Badge, UserBadge, UserProfile,
)
from .services import (
    compute_current_streak, compute_longest_streak,
    check_and_award_badges, get_recommendations,
)


class ModelRelationshipTests(TestCase):
    """Verify foreign keys and related_name lookups work correctly."""

    def setUp(self):
        self.style = BeerStyle.objects.create(name="IPA", family="Ale")
        self.brewery = Brewery.objects.create(name="Test Brewery", country="US")
        self.beer = Beer.objects.create(
            name="Test IPA", style=self.style, brewery=self.brewery,
            abv=6.5, avg_rating=4.0,
        )
        self.user = User.objects.create_user("testuser", password="testpass123")

    def test_beer_belongs_to_style(self):
        self.assertEqual(self.beer.style, self.style)
        self.assertIn(self.beer, self.style.beers.all())

    def test_beer_belongs_to_brewery(self):
        self.assertEqual(self.beer.brewery, self.brewery)
        self.assertIn(self.beer, self.brewery.beers.all())

    def test_user_profile_auto_created(self):
        self.assertTrue(hasattr(self.user, "profile"))
        self.assertIsInstance(self.user.profile, UserProfile)

    def test_checkin_links_user_and_beer(self):
        checkin = CheckIn.objects.create(
            user=self.user, beer=self.beer, rating=4, quantity=1,
        )
        self.assertEqual(checkin.user, self.user)
        self.assertEqual(checkin.beer, self.beer)
        self.assertIn(checkin, self.user.checkins.all())
        self.assertIn(checkin, self.beer.checkins.all())


class ConstraintTests(TestCase):
    """Verify database-level constraints enforce data integrity."""

    def setUp(self):
        self.user1 = User.objects.create_user("user1", password="pass123")
        self.user2 = User.objects.create_user("user2", password="pass123")
        self.style = BeerStyle.objects.create(name="Stout", family="Stout & Porter")
        self.brewery = Brewery.objects.create(name="Dark Brewery")
        self.beer = Beer.objects.create(
            name="Dark Beer", style=self.style, brewery=self.brewery,
        )

    def test_duplicate_follow_rejected(self):
        Follow.objects.create(follower=self.user1, followed=self.user2)
        with self.assertRaises(IntegrityError):
            Follow.objects.create(follower=self.user1, followed=self.user2)

    def test_self_follow_rejected(self):
        with self.assertRaises(IntegrityError):
            Follow.objects.create(follower=self.user1, followed=self.user1)

    def test_duplicate_badge_award_rejected(self):
        badge = Badge.objects.create(
            name="First Beer", badge_type="beers", threshold=1,
        )
        UserBadge.objects.create(user=self.user1, badge=badge)
        with self.assertRaises(IntegrityError):
            UserBadge.objects.create(user=self.user1, badge=badge)

    def test_rating_constraint(self):
        with self.assertRaises(IntegrityError):
            CheckIn.objects.create(
                user=self.user1, beer=self.beer, rating=0, quantity=1,
            )

    def test_quantity_constraint(self):
        with self.assertRaises(IntegrityError):
            CheckIn.objects.create(
                user=self.user1, beer=self.beer, rating=3, quantity=0,
            )


class StreakTests(TestCase):
    """Test streak computation logic."""

    def setUp(self):
        self.user = User.objects.create_user("streaker", password="pass123")
        self.style = BeerStyle.objects.create(name="Lager", family="Lager")
        self.brewery = Brewery.objects.create(name="Streak Brewery")
        self.beer = Beer.objects.create(
            name="Streak Lager", style=self.style, brewery=self.brewery,
        )

    def _checkin_on(self, days_ago):
        ci = CheckIn.objects.create(
            user=self.user, beer=self.beer, rating=3, quantity=1,
        )
        ci.created_at = timezone.now() - timedelta(days=days_ago)
        CheckIn.objects.filter(pk=ci.pk).update(created_at=ci.created_at)

    def test_no_checkins_zero_streak(self):
        self.assertEqual(compute_current_streak(self.user), 0)
        self.assertEqual(compute_longest_streak(self.user), 0)

    def test_today_only_streak_one(self):
        self._checkin_on(0)
        self.assertEqual(compute_current_streak(self.user), 1)

    def test_consecutive_days(self):
        for d in range(5):
            self._checkin_on(d)
        self.assertEqual(compute_current_streak(self.user), 5)

    def test_broken_streak(self):
        self._checkin_on(0)
        self._checkin_on(1)
        # Skip day 2
        self._checkin_on(3)
        self._checkin_on(4)
        self.assertEqual(compute_current_streak(self.user), 2)
        self.assertEqual(compute_longest_streak(self.user), 2)


class BadgeAwardTests(TestCase):
    """Test badge awarding after check-ins."""

    def setUp(self):
        self.user = User.objects.create_user("badger", password="pass123")
        self.style = BeerStyle.objects.create(name="Wheat", family="Wheat")
        self.brewery = Brewery.objects.create(name="Badge Brewery")
        Badge.objects.create(
            name="First Beer", badge_type="beers", threshold=1,
        )
        Badge.objects.create(
            name="Five Beers", badge_type="beers", threshold=5,
        )

    def _make_beer(self, name):
        return Beer.objects.create(
            name=name, style=self.style, brewery=self.brewery,
        )

    def test_badge_awarded_on_first_checkin(self):
        beer = self._make_beer("Beer 1")
        CheckIn.objects.create(user=self.user, beer=beer, rating=4)
        check_and_award_badges(self.user)
        self.assertTrue(
            UserBadge.objects.filter(user=self.user, badge__name="First Beer").exists()
        )

    def test_badge_not_awarded_prematurely(self):
        beer = self._make_beer("Beer 1")
        CheckIn.objects.create(user=self.user, beer=beer, rating=4)
        check_and_award_badges(self.user)
        self.assertFalse(
            UserBadge.objects.filter(user=self.user, badge__name="Five Beers").exists()
        )

    def test_badge_idempotent(self):
        beer = self._make_beer("Beer 1")
        CheckIn.objects.create(user=self.user, beer=beer, rating=4)
        check_and_award_badges(self.user)
        check_and_award_badges(self.user)  # second call should not error
        self.assertEqual(
            UserBadge.objects.filter(user=self.user, badge__name="First Beer").count(), 1
        )


class RecommendationTests(TestCase):
    """Test the recommendation engine."""

    def setUp(self):
        self.user = User.objects.create_user("taster", password="pass123")
        self.ipa_style = BeerStyle.objects.create(name="IPA", family="Ale")
        self.stout_style = BeerStyle.objects.create(name="Stout", family="Stout & Porter")
        self.brewery = Brewery.objects.create(name="Rec Brewery")

    def test_cold_start_returns_top_rated(self):
        Beer.objects.create(
            name="Top Beer", style=self.ipa_style, brewery=self.brewery, avg_rating=5.0,
        )
        recs = get_recommendations(self.user, limit=5)
        self.assertTrue(len(recs) > 0)

    def test_recommends_untried_beers_in_preferred_style(self):
        tried_beer = Beer.objects.create(
            name="Tried IPA", style=self.ipa_style, brewery=self.brewery, avg_rating=4.0,
        )
        tried_beer2 = Beer.objects.create(
            name="Tried IPA 2", style=self.ipa_style, brewery=self.brewery, avg_rating=4.0,
        )
        untried_beer = Beer.objects.create(
            name="Untried IPA", style=self.ipa_style, brewery=self.brewery, avg_rating=4.5,
        )
        CheckIn.objects.create(user=self.user, beer=tried_beer, rating=5)
        CheckIn.objects.create(user=self.user, beer=tried_beer2, rating=5)

        recs = get_recommendations(self.user, limit=5)
        rec_ids = [r.id for r in recs]
        self.assertIn(untried_beer.id, rec_ids)
        self.assertNotIn(tried_beer.id, rec_ids)


class ViewStatusCodeTests(TestCase):
    """Verify key views return 200."""

    def setUp(self):
        self.client = Client()
        self.style = BeerStyle.objects.create(name="Pilsner", family="Lager")
        self.brewery = Brewery.objects.create(name="View Brewery")
        self.beer = Beer.objects.create(
            name="View Pilsner", style=self.style, brewery=self.brewery,
            abv=5.0, avg_rating=3.8,
        )
        self.user = User.objects.create_user("viewer", password="pass123")

    def test_beer_list(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)

    def test_beer_detail(self):
        resp = self.client.get(f"/beer/{self.beer.pk}/")
        self.assertEqual(resp.status_code, 200)

    def test_leaderboard(self):
        resp = self.client.get("/leaderboard/")
        self.assertEqual(resp.status_code, 200)

    def test_style_list(self):
        resp = self.client.get("/styles/")
        self.assertEqual(resp.status_code, 200)

    def test_style_detail(self):
        resp = self.client.get(f"/styles/{self.style.pk}/")
        self.assertEqual(resp.status_code, 200)

    def test_user_search(self):
        resp = self.client.get("/users/")
        self.assertEqual(resp.status_code, 200)

    def test_passport_requires_login(self):
        resp = self.client.get("/passport/")
        self.assertEqual(resp.status_code, 302)  # redirect to login

    def test_passport_authenticated(self):
        self.client.login(username="viewer", password="pass123")
        resp = self.client.get("/passport/")
        self.assertEqual(resp.status_code, 200)

    def test_register_page(self):
        resp = self.client.get("/register/")
        self.assertEqual(resp.status_code, 200)

    def test_map(self):
        resp = self.client.get("/map/")
        self.assertEqual(resp.status_code, 200)
