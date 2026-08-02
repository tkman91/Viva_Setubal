"""Backend tests for Cargos (Roles) & Staff RBAC.

Auth model: login sets httpOnly cookie 'access_token'. Use requests.Session.
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@restaurante.pt")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")


def _new_session(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin():
    return _new_session(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def created_ids():
    ids = {"roles": [], "staff": []}
    yield ids
    s = _new_session(ADMIN_EMAIL, ADMIN_PASSWORD)
    for sid in ids["staff"]:
        s.delete(f"{API}/staff/{sid}")
    for rid in ids["roles"]:
        s.delete(f"{API}/roles/{rid}")


# ---------- Roles listing / system role ----------
def test_roles_list_contains_system_admin(admin):
    r = admin.get(f"{API}/roles")
    assert r.status_code == 200
    roles = r.json()
    admin_role = next((x for x in roles if x["name"] == "Administrador"), None)
    assert admin_role is not None
    assert admin_role["is_system"] is True
    assert admin_role["is_admin"] is True


def test_system_role_cannot_be_updated(admin):
    roles = admin.get(f"{API}/roles").json()
    sys_role = next(x for x in roles if x.get("is_system"))
    r = admin.put(f"{API}/roles/{sys_role['id']}", json={"name": "Hacked", "modules": ["stock"], "is_supervisor": False})
    assert r.status_code == 403


def test_system_role_cannot_be_deleted(admin):
    roles = admin.get(f"{API}/roles").json()
    sys_role = next(x for x in roles if x.get("is_system"))
    r = admin.delete(f"{API}/roles/{sys_role['id']}")
    assert r.status_code == 403


def test_create_custom_role(admin, created_ids):
    payload = {"name": f"TEST_Chefe_{uuid.uuid4().hex[:6]}", "modules": ["stock", "consumo"], "is_supervisor": True}
    r = admin.post(f"{API}/roles", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["name"] == payload["name"]
    assert set(data["modules"]) == {"stock", "consumo"}
    assert data["is_supervisor"] is True
    assert data["is_admin"] is False
    assert data["is_system"] is False
    created_ids["roles"].append(data["id"])

    listing = admin.get(f"{API}/roles").json()
    assert any(x["id"] == data["id"] for x in listing)


def test_update_custom_role(admin, created_ids):
    payload = {"name": f"TEST_Editor_{uuid.uuid4().hex[:6]}", "modules": ["stock"], "is_supervisor": False}
    rid = admin.post(f"{API}/roles", json=payload).json()["id"]
    created_ids["roles"].append(rid)
    upd = {"name": payload["name"] + "_v2", "modules": ["stock", "picagem", "consumo"], "is_supervisor": True}
    r2 = admin.put(f"{API}/roles/{rid}", json=upd)
    assert r2.status_code == 200, r2.text
    got = r2.json()
    assert got["name"] == upd["name"]
    assert set(got["modules"]) == set(upd["modules"])
    assert got["is_supervisor"] is True


def test_create_staff_and_rbac_derivation(admin, created_ids):
    role = admin.post(
        f"{API}/roles",
        json={"name": f"TEST_Sup_{uuid.uuid4().hex[:6]}", "modules": ["consumo", "picagem"], "is_supervisor": True},
    ).json()
    created_ids["roles"].append(role["id"])

    email = f"TEST_user_{uuid.uuid4().hex[:6]}@test.pt"
    password = "test1234"
    staff = admin.post(
        f"{API}/staff",
        json={"name": "TEST Employee", "email": email, "password": password, "role_id": role["id"], "hourly_wage": 10.0},
    )
    assert staff.status_code == 200, staff.text
    s = staff.json()
    assert s["role_id"] == role["id"]
    created_ids["staff"].append(s["id"])

    user_sess = _new_session(email, password)
    me = user_sess.get(f"{API}/auth/me").json()
    assert me["is_admin"] is False
    assert me["is_supervisor"] is True
    assert set(me["permissions"]) == {"consumo", "picagem"}
    assert me["role_id"] == role["id"]

    # non-admin can list roles
    assert user_sess.get(f"{API}/roles").status_code == 200

    # non-admin cannot mutate roles
    assert user_sess.post(f"{API}/roles", json={"name": "TEST_x", "modules": [], "is_supervisor": False}).status_code == 403
    assert user_sess.delete(f"{API}/roles/{role['id']}").status_code == 403
    assert user_sess.put(f"{API}/roles/{role['id']}", json={"name": "TEST_x", "modules": [], "is_supervisor": False}).status_code == 403

    # non-admin cannot create staff
    assert user_sess.post(f"{API}/staff", json={"name": "x", "email": "x@x.pt", "password": "abc", "role_id": role["id"], "hourly_wage": 0}).status_code == 403


def test_delete_role_in_use_returns_400(admin, created_ids):
    role = admin.post(
        f"{API}/roles",
        json={"name": f"TEST_InUse_{uuid.uuid4().hex[:6]}", "modules": ["stock"], "is_supervisor": False},
    ).json()
    created_ids["roles"].append(role["id"])
    email = f"TEST_inuse_{uuid.uuid4().hex[:6]}@test.pt"
    s = admin.post(
        f"{API}/staff",
        json={"name": "TEST InUse", "email": email, "password": "test1234", "role_id": role["id"], "hourly_wage": 0},
    ).json()
    created_ids["staff"].append(s["id"])
    r = admin.delete(f"{API}/roles/{role['id']}")
    assert r.status_code == 400
    detail = (r.json().get("detail") or "").lower()
    assert "uso" in detail


def test_update_staff_role_id_reassigns_permissions(admin, created_ids):
    r_a = admin.post(f"{API}/roles", json={"name": f"TEST_A_{uuid.uuid4().hex[:6]}", "modules": ["stock"], "is_supervisor": False}).json()
    created_ids["roles"].append(r_a["id"])
    r_b = admin.post(f"{API}/roles", json={"name": f"TEST_B_{uuid.uuid4().hex[:6]}", "modules": ["consumo", "relatorios"], "is_supervisor": True}).json()
    created_ids["roles"].append(r_b["id"])
    email = f"TEST_swap_{uuid.uuid4().hex[:6]}@test.pt"
    s = admin.post(f"{API}/staff", json={"name": "TEST Swap", "email": email, "password": "test1234", "role_id": r_a["id"], "hourly_wage": 0}).json()
    created_ids["staff"].append(s["id"])

    r = admin.put(f"{API}/staff/{s['id']}", json={"name": "TEST Swap", "email": email, "role_id": r_b["id"], "hourly_wage": 0})
    assert r.status_code == 200, r.text
    assert r.json()["role_id"] == r_b["id"]

    tok = _new_session(email, "test1234")
    me = tok.get(f"{API}/auth/me").json()
    assert set(me["permissions"]) == {"consumo", "relatorios"}
    assert me["is_supervisor"] is True


def test_duplicate_role_name_rejected(admin, created_ids):
    name = f"TEST_Dup_{uuid.uuid4().hex[:6]}"
    r1 = admin.post(f"{API}/roles", json={"name": name, "modules": [], "is_supervisor": False})
    assert r1.status_code == 200
    created_ids["roles"].append(r1.json()["id"])
    r2 = admin.post(f"{API}/roles", json={"name": name, "modules": [], "is_supervisor": False})
    assert r2.status_code == 400


def test_role_invalid_modules_are_filtered(admin, created_ids):
    r = admin.post(f"{API}/roles", json={"name": f"TEST_Filt_{uuid.uuid4().hex[:6]}", "modules": ["stock", "bogus", "consumo"], "is_supervisor": False}).json()
    created_ids["roles"].append(r["id"])
    assert "bogus" not in r["modules"]
    assert set(r["modules"]) == {"stock", "consumo"}
