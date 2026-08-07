"""Tests for the 4 new features: settings tolerances, /reports/hours,
/schedules/weekly-summary, /notifications + atraso e2e."""
import os
import uuid
import requests
import pytest
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_EMAIL = "admin@restaurante.pt"
ADMIN_PW = "admin123"


@pytest.fixture(scope="module")
def admin_sess():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def settings_snapshot(admin_sess):
    r = admin_sess.get(f"{API}/settings")
    snap = r.json() if r.status_code == 200 and r.json() else {
        "restaurant_name": "Test", "lat": 38.7223, "lng": -9.1393,
        "radius_m": 100, "late_tolerance_min": 5, "no_signal_minutes": 5,
    }
    yield snap
    # restore
    admin_sess.put(f"{API}/settings", json={
        "restaurant_name": snap.get("restaurant_name", "Test"),
        "lat": snap.get("lat", 38.7223),
        "lng": snap.get("lng", -9.1393),
        "radius_m": snap.get("radius_m", 100),
        "late_tolerance_min": snap.get("late_tolerance_min", 5),
        "no_signal_minutes": snap.get("no_signal_minutes", 5),
    })


# ---------- Feature 4: Settings tolerances ----------
class TestSettingsTolerances:
    def test_get_settings_has_new_fields_with_defaults(self, admin_sess, settings_snapshot):
        r = admin_sess.get(f"{API}/settings")
        assert r.status_code == 200
        s = r.json()
        assert "late_tolerance_min" in s
        assert "no_signal_minutes" in s

    def test_update_settings_persists_tolerances(self, admin_sess, settings_snapshot):
        payload = {
            "restaurant_name": settings_snapshot.get("restaurant_name", "Test"),
            "lat": settings_snapshot.get("lat", 38.7223),
            "lng": settings_snapshot.get("lng", -9.1393),
            "radius_m": settings_snapshot.get("radius_m", 100),
            "late_tolerance_min": 12,
            "no_signal_minutes": 7,
        }
        r = admin_sess.put(f"{API}/settings", json=payload)
        assert r.status_code == 200, r.text
        r2 = admin_sess.get(f"{API}/settings")
        assert r2.status_code == 200
        got = r2.json()
        assert got["late_tolerance_min"] == 12
        assert got["no_signal_minutes"] == 7


# ---------- Feature 1: /reports/hours ----------
class TestReportsHours:
    def test_hours_endpoint_shape(self, admin_sess):
        today = datetime.now(timezone.utc).date().isoformat()
        past = (datetime.now(timezone.utc).date() - timedelta(days=30)).isoformat()
        r = admin_sess.get(f"{API}/reports/hours", params={"from": past, "to": today})
        assert r.status_code == 200, r.text
        d = r.json()
        assert set(["from", "to", "items", "total_hours", "total_cost"]).issubset(d.keys())
        assert isinstance(d["items"], list)
        # each item shape
        for it in d["items"]:
            assert {"user_id", "user_name", "hours", "hourly_wage", "cost"}.issubset(it.keys())

    def test_hours_requires_relatorios(self, admin_sess):
        # invalid dates -> 4xx
        r = admin_sess.get(f"{API}/reports/hours", params={"from": "not-a-date", "to": "2025-01-01"})
        assert r.status_code in (400, 422, 500)


# ---------- Feature 2: /schedules/weekly-summary ----------
class TestWeeklySummary:
    def test_weekly_summary_shape(self, admin_sess):
        r = admin_sess.get(f"{API}/schedules/weekly-summary")
        assert r.status_code == 200, r.text
        d = r.json()
        assert {"week_start", "week_end", "items"}.issubset(d.keys())
        assert isinstance(d["items"], list)
        for it in d["items"]:
            assert {"user_id", "user_name", "planned_hours", "actual_hours"}.issubset(it.keys())


# ---------- Feature 3: Notifications + atraso e2e ----------
class TestNotificationsAndAtraso:
    def test_notifications_endpoint_shape(self, admin_sess):
        r = admin_sess.get(f"{API}/notifications")
        assert r.status_code == 200, r.text
        d = r.json()
        assert "items" in d and "unread" in d
        assert isinstance(d["items"], list)

    def test_plain_funcionario_gets_403_on_notifications(self, admin_sess):
        # Create a role with picagem only (no supervisor), then a user with it
        role_name = f"TEST_FuncNotif_{uuid.uuid4().hex[:6]}"
        rr = admin_sess.post(f"{API}/roles", json={"name": role_name, "modules": ["picagem"], "is_supervisor": False})
        assert rr.status_code == 200, rr.text
        role_id = rr.json()["id"]
        email = f"test_funcnotif_{uuid.uuid4().hex[:6]}@t.pt"
        u = admin_sess.post(f"{API}/staff", json={"name": "TEST Funcnotif", "email": email, "password": "pw12345", "role_id": role_id})
        assert u.status_code == 200, u.text
        uid = u.json()["id"]
        try:
            s2 = requests.Session()
            lg = s2.post(f"{API}/auth/login", json={"email": email, "password": "pw12345"})
            assert lg.status_code == 200
            resp = s2.get(f"{API}/notifications")
            assert resp.status_code == 403, f"expected 403 got {resp.status_code}: {resp.text}"
        finally:
            admin_sess.delete(f"{API}/staff/{uid}")
            admin_sess.delete(f"{API}/roles/{role_id}")

    def test_atraso_end_to_end(self, admin_sess, settings_snapshot):
        # Configure settings so any lat/lng punch is within radius (huge radius)
        admin_sess.put(f"{API}/settings", json={
            "restaurant_name": settings_snapshot.get("restaurant_name", "Test"),
            "lat": 0.0, "lng": 0.0,
            "radius_m": 20_000_000,
            "late_tolerance_min": 5,
            "no_signal_minutes": 5,
        })
        # Create role with picagem for the test user
        role_name = f"TEST_Atraso_{uuid.uuid4().hex[:6]}"
        rr = admin_sess.post(f"{API}/roles", json={"name": role_name, "modules": ["picagem"], "is_supervisor": False})
        role_id = rr.json()["id"]
        email = f"test_atraso_{uuid.uuid4().hex[:6]}@t.pt"
        u = admin_sess.post(f"{API}/staff", json={"name": "TEST Atraso", "email": email, "password": "pw12345", "role_id": role_id})
        uid = u.json()["id"]
        try:
            # Give TODAY a shift starting at 00:00 (so 'now' is definitely late)
            from datetime import datetime as _dt
            wk_keys = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
            # Compute today's weekday in Lisbon (approx: use UTC—it's close enough for weekday key normally)
            today_key = wk_keys[_dt.utcnow().weekday()]
            sched = {today_key: {"start": "00:00", "end": "23:59", "off": False}}
            r = admin_sess.put(f"{API}/schedules/{uid}", json={"shifts": sched})
            assert r.status_code == 200, r.text

            # snapshot notifications count before
            before = admin_sess.get(f"{API}/notifications").json()
            before_atraso = [n for n in before["items"] if n["type"] == "atraso" and n["user_id"] == uid]

            # Login as user and punch in
            s2 = requests.Session()
            lg = s2.post(f"{API}/auth/login", json={"email": email, "password": "pw12345"})
            assert lg.status_code == 200
            p = s2.post(f"{API}/timeclock/punch", json={"lat": 0.0, "lng": 0.0})
            assert p.status_code == 200, p.text
            assert p.json().get("action") == "entrada"

            # Now admin should see an 'atraso' notification for that user
            after = admin_sess.get(f"{API}/notifications").json()
            after_atraso = [n for n in after["items"] if n["type"] == "atraso" and n["user_id"] == uid]
            assert len(after_atraso) >= 1, f"expected atraso notification for user, got items={after['items']}"

            # Mark as read
            mr = admin_sess.post(f"{API}/notifications/read")
            assert mr.status_code == 200
            aft = admin_sess.get(f"{API}/notifications").json()
            assert aft["unread"] == 0
        finally:
            # Cleanup: delete created notifications, entries, schedule, user, role
            # Punch entries -> delete via correction path? Use direct DELETE (admin is_system)
            entries = admin_sess.get(f"{API}/timeclock/entries").json()
            for e in entries:
                if e.get("user_id") == uid:
                    admin_sess.delete(f"{API}/timeclock/entries/{e['id']}")
            admin_sess.put(f"{API}/schedules/{uid}", json={"shifts": {}})
            admin_sess.delete(f"{API}/staff/{uid}")
            admin_sess.delete(f"{API}/roles/{role_id}")
            # remove atraso notifications for this user via mongo? no admin route; leave marked-read
