"""Backend tests for two-tier system role hierarchy (Administrador rank100 > Dono/a rank90).

Verifies:
- Both system roles exist, protected, is_admin
- Dono cannot edit/delete Administrador cargo
- Dono cannot assign Administrador cargo
- Dono cannot edit/delete an Administrador user account
- Administrador CAN manage Dono users
- Dono can create/edit/delete non-system roles
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@restaurante.pt")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
DONO_EMAIL = "dono_test_htier@restaurante.pt"
DONO_PASSWORD = "dono1234"


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text}"
    return s, r.json()["user"]


@pytest.fixture(scope="module")
def admin_ctx():
    s, u = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    return s, u


@pytest.fixture(scope="module")
def roles_map(admin_ctx):
    s, _ = admin_ctx
    r = s.get(f"{API}/roles")
    assert r.status_code == 200
    return {x["name"]: x for x in r.json()}


@pytest.fixture(scope="module")
def dono_user(admin_ctx, roles_map):
    s, _ = admin_ctx
    # Cleanup if exists
    staff = s.get(f"{API}/staff").json()
    existing = next((x for x in staff if x["email"] == DONO_EMAIL), None)
    if existing:
        s.delete(f"{API}/staff/{existing['id']}")
    dono_role = roles_map["Dono/a"]
    r = s.post(f"{API}/staff", json={
        "name": "Dono Teste",
        "email": DONO_EMAIL,
        "password": DONO_PASSWORD,
        "role_id": dono_role["id"],
        "hourly_wage": 0.0,
    })
    assert r.status_code == 200, r.text
    created = r.json()
    yield created
    # teardown
    s2, _ = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    s2.delete(f"{API}/staff/{created['id']}")


def test_two_system_roles_exist_protected(roles_map):
    admin = roles_map.get("Administrador")
    dono = roles_map.get("Dono/a")
    assert admin and dono
    assert admin["is_system"] is True and admin["is_admin"] is True
    assert dono["is_system"] is True and dono["is_admin"] is True
    assert admin["rank"] == 100
    assert dono["rank"] == 90


def test_dono_login_returns_admin_flags(dono_user):
    _, u = _login(DONO_EMAIL, DONO_PASSWORD)
    assert u["is_admin"] is True
    assert u["is_supervisor"] is True
    assert u["rank"] == 90
    # Should have all modules
    assert set(u["permissions"]) >= {"stock", "picagem", "staff", "consumo", "faturacao", "relatorios"}


def test_dono_cannot_edit_administrador_role(dono_user, roles_map):
    s, _ = _login(DONO_EMAIL, DONO_PASSWORD)
    admin_role = roles_map["Administrador"]
    r = s.put(f"{API}/roles/{admin_role['id']}", json={"name": "Hack", "modules": ["stock"], "is_supervisor": False})
    assert r.status_code == 403


def test_dono_cannot_delete_administrador_role(dono_user, roles_map):
    s, _ = _login(DONO_EMAIL, DONO_PASSWORD)
    admin_role = roles_map["Administrador"]
    r = s.delete(f"{API}/roles/{admin_role['id']}")
    assert r.status_code == 403


def test_dono_cannot_assign_administrador_cargo(dono_user, roles_map):
    s, _ = _login(DONO_EMAIL, DONO_PASSWORD)
    admin_role = roles_map["Administrador"]
    payload = {
        "name": "should not create",
        "email": f"nope_{uuid.uuid4().hex[:6]}@t.pt",
        "password": "xx123456",
        "role_id": admin_role["id"],
        "hourly_wage": 0.0,
    }
    r = s.post(f"{API}/staff", json=payload)
    assert r.status_code == 403


def test_dono_cannot_edit_admin_account(dono_user):
    s, _ = _login(DONO_EMAIL, DONO_PASSWORD)
    staff = s.get(f"{API}/staff").json()
    admin_acc = next(x for x in staff if x["email"] == ADMIN_EMAIL)
    r = s.put(f"{API}/staff/{admin_acc['id']}", json={"name": "Renamed"})
    assert r.status_code == 403


def test_dono_cannot_delete_admin_account(dono_user):
    s, _ = _login(DONO_EMAIL, DONO_PASSWORD)
    staff = s.get(f"{API}/staff").json()
    admin_acc = next(x for x in staff if x["email"] == ADMIN_EMAIL)
    r = s.delete(f"{API}/staff/{admin_acc['id']}")
    assert r.status_code == 403


def test_admin_can_manage_dono_account(admin_ctx, dono_user):
    s, _ = admin_ctx
    r = s.put(f"{API}/staff/{dono_user['id']}", json={"phone": "912345678"})
    assert r.status_code == 200
    assert r.json().get("phone") == "912345678"


def test_dono_can_create_and_delete_custom_role(dono_user):
    s, _ = _login(DONO_EMAIL, DONO_PASSWORD)
    name = f"TEST_CustomByDono_{uuid.uuid4().hex[:6]}"
    r = s.post(f"{API}/roles", json={"name": name, "modules": ["stock"], "is_supervisor": False})
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    r2 = s.delete(f"{API}/roles/{rid}")
    assert r2.status_code == 200
