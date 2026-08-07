"""Backend tests: Picagem tabs — Horário (schedules), Compliance, Correção de picagens, Delete gating.

Verifies:
- GET/PUT /api/schedules
- GET /api/schedules/compliance (Presente / Atraso / Falta)
- PUT /api/timeclock/entries/{id} — close & edit; validates saída >= entrada (400)
- DELETE /api/timeclock/entries/{id} — 200 for system role (Administrador), 403 for non-system manager
- RBAC: manager-non-system sees schedules; plain funcionário 403 on manager endpoints
"""
import os
import uuid
import time
from datetime import datetime, timedelta, timezone

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_EMAIL = "admin@restaurante.pt"
ADMIN_PASSWORD = "admin123"

MGR_EMAIL = f"mgr_pic_{uuid.uuid4().hex[:6]}@rest.pt"
MGR_PASS = "mgrpass123"
FUNC_EMAIL = f"func_pic_{uuid.uuid4().hex[:6]}@rest.pt"
FUNC_PASS = "funcpass123"


def _login(email, pwd):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pwd}, timeout=15)
    assert r.status_code == 200, f"login {email} failed {r.status_code} {r.text}"
    return s, r.json()["user"]


@pytest.fixture(scope="module")
def admin_ctx():
    s, u = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    assert u.get("is_system") is True, "Admin should be is_system=True"
    return s, u


@pytest.fixture(scope="module")
def created_roles(admin_ctx):
    """Creates a manager role (picagem+supervision) and a plain funcionário role (picagem, no supervision)."""
    s, _ = admin_ctx
    mgr_name = f"TEST_MgrPic_{uuid.uuid4().hex[:6]}"
    func_name = f"TEST_FuncPic_{uuid.uuid4().hex[:6]}"
    r1 = s.post(f"{API}/roles", json={"name": mgr_name, "modules": ["picagem"], "is_supervisor": True})
    assert r1.status_code == 200, r1.text
    r2 = s.post(f"{API}/roles", json={"name": func_name, "modules": ["picagem"], "is_supervisor": False})
    assert r2.status_code == 200, r2.text
    mgr_role = r1.json()
    func_role = r2.json()
    yield mgr_role, func_role
    # cleanup
    s.delete(f"{API}/roles/{mgr_role['id']}")
    s.delete(f"{API}/roles/{func_role['id']}")


@pytest.fixture(scope="module")
def created_users(admin_ctx, created_roles):
    s, _ = admin_ctx
    mgr_role, func_role = created_roles
    # cleanup existing (unlikely, random emails)
    r = s.post(f"{API}/staff", json={
        "name": "TEST Manager Picagem", "email": MGR_EMAIL, "password": MGR_PASS,
        "role_id": mgr_role["id"], "hourly_wage": 0.0,
    })
    assert r.status_code == 200, r.text
    mgr = r.json()
    r = s.post(f"{API}/staff", json={
        "name": "TEST Func Picagem", "email": FUNC_EMAIL, "password": FUNC_PASS,
        "role_id": func_role["id"], "hourly_wage": 0.0,
    })
    assert r.status_code == 200, r.text
    func = r.json()
    yield mgr, func
    s.delete(f"{API}/staff/{mgr['id']}")
    s.delete(f"{API}/staff/{func['id']}")


# ---------- /auth/me exposes is_system ----------
def test_admin_is_system_true(admin_ctx):
    s, u = admin_ctx
    r = s.get(f"{API}/auth/me")
    assert r.status_code == 200
    assert r.json().get("is_system") is True


def test_manager_non_system_is_system_false(created_users):
    mgr, _ = created_users
    s, u = _login(MGR_EMAIL, MGR_PASS)
    assert u.get("is_system") is False
    assert u.get("is_supervisor") is True


# ---------- Schedules GET/PUT ----------
def test_list_schedules_admin(admin_ctx):
    s, _ = admin_ctx
    r = s.get(f"{API}/schedules")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list) and len(data) > 0
    row = data[0]
    for k in ("user_id", "user_name", "shifts"):
        assert k in row


def test_put_schedule_persists(admin_ctx, created_users):
    s, _ = admin_ctx
    _, func = created_users
    payload = {"shifts": {
        "mon": {"start": "09:00", "end": "17:00", "off": False},
        "sun": {"off": True},
    }}
    r = s.put(f"{API}/schedules/{func['id']}", json=payload)
    assert r.status_code == 200, r.text
    assert r.json()["shifts"]["mon"]["start"] == "09:00"

    # GET verifies persistence
    lst = s.get(f"{API}/schedules").json()
    row = next(x for x in lst if x["user_id"] == func["id"])
    assert row["shifts"]["mon"]["end"] == "17:00"
    assert row["shifts"]["sun"]["off"] is True


def test_schedule_manager_can_write(created_users):
    ms, _ = _login(MGR_EMAIL, MGR_PASS)
    _, func = created_users
    r = ms.put(f"{API}/schedules/{func['id']}", json={"shifts": {"tue": {"start": "10:00", "end": "18:00"}}})
    assert r.status_code == 200


def test_schedule_funcionario_forbidden(created_users):
    fs, _ = _login(FUNC_EMAIL, FUNC_PASS)
    r = fs.get(f"{API}/schedules")
    assert r.status_code == 403


# ---------- Compliance ----------
def test_compliance_falta_when_no_punch(admin_ctx, created_users):
    """Set today's shift for func → expect 'falta' since no punch."""
    s, _ = admin_ctx
    _, func = created_users
    from zoneinfo import ZoneInfo
    lisbon = ZoneInfo("Europe/Lisbon")
    today = datetime.now(lisbon).date()
    keys = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    wk = keys[today.weekday()]
    s.put(f"{API}/schedules/{func['id']}", json={"shifts": {wk: {"start": "08:00", "end": "16:00"}}})
    r = s.get(f"{API}/schedules/compliance?date={today.isoformat()}")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["weekday"] == wk
    item = next((x for x in data["items"] if x["user_id"] == func["id"]), None)
    assert item is not None, f"No item for func on {today}. items={data['items']}"
    # No punch expected → falta
    if item["actual_in"] is None:
        assert item["status"] == "falta"


def test_compliance_default_today(admin_ctx):
    s, _ = admin_ctx
    r = s.get(f"{API}/schedules/compliance")
    assert r.status_code == 200
    from zoneinfo import ZoneInfo
    lisbon = ZoneInfo("Europe/Lisbon")
    assert r.json()["date"] == datetime.now(lisbon).date().isoformat()


# ---------- Correction (edit/close) ----------
@pytest.fixture
def open_entry(admin_ctx, created_users):
    """Have func punch in to create an open entry, then fetch it."""
    s_admin, _ = admin_ctx
    _, func = created_users
    settings = s_admin.get(f"{API}/settings").json() if s_admin.get(f"{API}/settings").status_code == 200 else None
    if not settings or not settings.get("lat"):
        pytest.skip("Restaurant location not configured")
    fs, _ = _login(FUNC_EMAIL, FUNC_PASS)
    r = fs.post(f"{API}/timeclock/punch", json={"lat": settings["lat"], "lng": settings["lng"]})
    if r.status_code != 200 or r.json().get("action") != "entrada":
        pytest.skip(f"Cannot open entry (already open or geofence): {r.status_code} {r.text}")
    # Fetch the newly created open entry for this func
    entries = s_admin.get(f"{API}/timeclock/entries").json()
    open_ = next((e for e in entries if e["user_id"] == func["id"] and not e.get("clock_out")), None)
    if not open_:
        pytest.skip("Open entry not found after punch")
    return open_


def test_close_open_entry_sets_reason_correction(admin_ctx, open_entry):
    s, _ = admin_ctx
    entry = open_entry
    assert entry.get("clock_out") in (None, "")
    # Close via correction
    co_local = (datetime.now() + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M")
    r = s.put(f"{API}/timeclock/entries/{entry['id']}", json={"clock_out": co_local})
    assert r.status_code == 200, r.text
    updated = r.json()
    assert updated.get("clock_out")
    assert updated.get("checkout_reason") == "correction"
    assert updated.get("duration_seconds", 0) > 0


def test_edit_closed_entry_recomputes_duration(admin_ctx, created_users):
    s, _ = admin_ctx
    entries = s.get(f"{API}/timeclock/entries").json()
    closed = next((e for e in entries if e.get("clock_out")), None)
    if not closed:
        pytest.skip("No closed entry available")
    # Send BOTH clock_in and clock_out 30 minutes apart in Lisbon local (naive datetime-local strings)
    ci = "2025-01-15T09:00"
    co = "2025-01-15T09:30"
    r = s.put(f"{API}/timeclock/entries/{closed['id']}", json={"clock_in": ci, "clock_out": co})
    assert r.status_code == 200, r.text
    dur = r.json().get("duration_seconds")
    assert dur is not None
    assert 1700 <= dur <= 1900, f"expected ~1800s got {dur}"


def test_saida_before_entrada_rejected(admin_ctx, created_users):
    s, _ = admin_ctx
    entries = s.get(f"{API}/timeclock/entries").json()
    if not entries:
        pytest.skip("No entries")
    e = entries[0]
    ci = datetime.now()
    co = ci - timedelta(hours=1)
    r = s.put(f"{API}/timeclock/entries/{e['id']}", json={
        "clock_in": ci.strftime("%Y-%m-%dT%H:%M"),
        "clock_out": co.strftime("%Y-%m-%dT%H:%M"),
    })
    assert r.status_code == 400
    assert "saída" in r.json().get("detail", "").lower() or "anterior" in r.json().get("detail", "").lower()


# ---------- Delete gating ----------
def test_delete_by_non_system_manager_forbidden(created_users):
    ms, _ = _login(MGR_EMAIL, MGR_PASS)
    # get any entry
    r = ms.get(f"{API}/timeclock/entries")
    assert r.status_code == 200
    entries = r.json()
    if not entries:
        pytest.skip("No entries to attempt delete")
    r = ms.delete(f"{API}/timeclock/entries/{entries[0]['id']}")
    assert r.status_code == 403


def test_delete_by_admin_system_ok(admin_ctx):
    s, _ = admin_ctx
    entries = s.get(f"{API}/timeclock/entries").json()
    # find a TEST entry (belonging to func we created) if possible
    target = None
    for e in entries:
        if e.get("user_name", "").startswith("TEST "):
            target = e
            break
    if not target:
        pytest.skip("No TEST entry to delete safely")
    r = s.delete(f"{API}/timeclock/entries/{target['id']}")
    assert r.status_code == 200
    # verify gone
    after = s.get(f"{API}/timeclock/entries").json()
    assert not any(e["id"] == target["id"] for e in after)


# ---------- Access control on correction endpoints ----------
def test_funcionario_cannot_correct(admin_ctx):
    fs, _ = _login(FUNC_EMAIL, FUNC_PASS)
    s, _ = admin_ctx
    entries = s.get(f"{API}/timeclock/entries").json()
    if not entries:
        pytest.skip("No entries")
    r = fs.put(f"{API}/timeclock/entries/{entries[0]['id']}", json={"clock_out": "2025-01-01T09:00"})
    assert r.status_code == 403
