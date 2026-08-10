"""Tests for the new Menus/Combos feature + RBAC."""
import os
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN = {"email": "admin@restaurante.pt", "password": "admin123"}


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=ADMIN)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def sample_product(admin):
    r = admin.get(f"{API}/products")
    assert r.status_code == 200
    prods = r.json()
    if prods:
        return prods[0]
    # create one
    r = admin.post(f"{API}/products", json={
        "name": "TEST_prod", "unit": "un", "current_stock": 100,
        "min_stock": 0, "cost_price": 1.0, "vat_rate": 23,
    })
    assert r.status_code in (200, 201), r.text
    return r.json()


class TestAdminModules:
    def test_admin_has_menus_permission(self, admin):
        r = admin.get(f"{API}/auth/me")
        assert r.status_code == 200
        me = r.json()
        assert "menus" in me.get("permissions", []), me


class TestCombosCRUDAdmin:
    def test_list_combos(self, admin):
        r = admin.get(f"{API}/pos/combos")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_edit_delete(self, admin, sample_product):
        payload = {
            "name": f"TEST_Menu_{uuid.uuid4().hex[:6]}",
            "price": 9.5, "vat_rate": 13, "active": True,
            "items": [{"product_id": sample_product["id"], "quantity": 1}],
        }
        r = admin.post(f"{API}/pos/combos", json=payload)
        assert r.status_code == 200, r.text
        combo = r.json()
        assert combo["name"] == payload["name"]
        assert combo["price"] == 9.5
        assert combo.get("id")

        # verify persisted
        r = admin.get(f"{API}/pos/combos")
        ids = [c["id"] for c in r.json()]
        assert combo["id"] in ids

        # edit
        upd = {**payload, "name": payload["name"] + "_upd", "price": 12.0}
        r = admin.put(f"{API}/pos/combos/{combo['id']}", json=upd)
        assert r.status_code == 200, r.text
        assert r.json()["price"] == 12.0
        assert r.json()["name"].endswith("_upd")

        # delete
        r = admin.delete(f"{API}/pos/combos/{combo['id']}")
        assert r.status_code == 200, r.text
        r = admin.get(f"{API}/pos/combos")
        assert combo["id"] not in [c["id"] for c in r.json()]


class TestRBACMenus:
    """A user without 'menus' module must get 403 on write, list should work."""

    @pytest.fixture(scope="class")
    def user_without_menus(self, admin):
        # create role with only stock (no menus)
        role_name = f"TEST_role_nomenus_{uuid.uuid4().hex[:6]}"
        r = admin.post(f"{API}/roles", json={
            "name": role_name, "modules": ["stock"], "is_supervisor": False,
        })
        assert r.status_code == 200, r.text
        role = r.json()
        # create user
        email = f"test_nomenus_{uuid.uuid4().hex[:6]}@example.com"
        r = admin.post(f"{API}/staff", json={
            "name": "TEST NoMenus", "email": email, "password": "test1234",
            "role_id": role["id"],
        })
        assert r.status_code == 200, r.text
        user = r.json()
        # login as new user
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json={"email": email, "password": "test1234"})
        assert r.status_code == 200, r.text

        yield s

        admin.delete(f"{API}/staff/{user['id']}")
        admin.delete(f"{API}/roles/{role['id']}")

    @pytest.fixture(scope="class")
    def user_with_menus(self, admin):
        role_name = f"TEST_role_menus_{uuid.uuid4().hex[:6]}"
        r = admin.post(f"{API}/roles", json={
            "name": role_name, "modules": ["menus"], "is_supervisor": False,
        })
        assert r.status_code == 200, r.text
        role = r.json()
        email = f"test_menus_{uuid.uuid4().hex[:6]}@example.com"
        r = admin.post(f"{API}/staff", json={
            "name": "TEST Menus", "email": email, "password": "test1234",
            "role_id": role["id"],
        })
        assert r.status_code == 200, r.text
        user = r.json()
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json={"email": email, "password": "test1234"})
        assert r.status_code == 200, r.text
        yield s
        admin.delete(f"{API}/staff/{user['id']}")
        admin.delete(f"{API}/roles/{role['id']}")

    def test_nomenus_list_allowed(self, user_without_menus):
        r = user_without_menus.get(f"{API}/pos/combos")
        # list is guarded only by get_current_user
        assert r.status_code == 200

    def test_nomenus_create_forbidden(self, user_without_menus, sample_product):
        r = user_without_menus.post(f"{API}/pos/combos", json={
            "name": "TEST_forbid", "price": 1, "vat_rate": 23, "active": True,
            "items": [{"product_id": sample_product["id"], "quantity": 1}],
        })
        assert r.status_code == 403, r.status_code

    def test_withmenus_create_allowed(self, user_with_menus, admin, sample_product):
        r = user_with_menus.post(f"{API}/pos/combos", json={
            "name": f"TEST_wm_{uuid.uuid4().hex[:6]}",
            "price": 5, "vat_rate": 23, "active": True,
            "items": [{"product_id": sample_product["id"], "quantity": 1}],
        })
        assert r.status_code == 200, r.text
        combo_id = r.json()["id"]
        # cleanup
        admin.delete(f"{API}/pos/combos/{combo_id}")


class TestModulesList:
    def test_roles_modules_include_menus(self, admin):
        # Verify the admin role has menus enabled
        r = admin.get(f"{API}/roles")
        assert r.status_code == 200
        roles = r.json()
        admin_role = next((x for x in roles if x.get("name") == "Administrador"), None)
        assert admin_role is not None
        # admin role has is_admin, so modules == MODULES
        assert "menus" in admin_role.get("modules", []) or admin_role.get("is_admin")
