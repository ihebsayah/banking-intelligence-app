import sys
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# Path setup
BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GATEWAY = os.path.join(BASE, "services/api_gateway")
SHARED = os.path.join(BASE, "services/shared")

for p in [GATEWAY, SHARED]:
    if p not in sys.path:
        sys.path.insert(0, p)

from fastapi.testclient import TestClient
from fastapi import Depends
from shared.models import User, UserRole

def make_db(fetch_one_return=None, fetch_all_return=None, execute_return="OK"):
    db = MagicMock()
    db.fetch_one = AsyncMock(return_value=fetch_one_return)
    db.fetch_all = AsyncMock(return_value=fetch_all_return or [])
    db.execute = AsyncMock(return_value=execute_return)
    db._pool = MagicMock()
    return db

@pytest.fixture(scope="module")
def app_and_tokens():
    import main as gw
    from auth import create_access_token, verify_token
    from routes import get_current_user, security
    
    client = TestClient(gw.app, raise_server_exceptions=False)
    tokens = {
        role: f"Bearer {create_access_token(f'{role}_001', role)[0]}"
        for role in ("analyst", "manager", "compliance", "admin")
    }
    
    async def override_get_current_user(credentials = Depends(security)):
        if not credentials:
             return User(user_id="anonymous", user_role="analyst", permissions=[])
        user_id, user_role = verify_token(credentials.credentials)
        ROLE_PERMISSIONS = {
            "analyst":    ["read:customers", "read:accounts", "read:transactions", "read:risk_flags"],
            "manager":    ["read:customers", "read:accounts", "read:transactions", "read:branch_data", "read:risk_summary"],
            "compliance": ["read:customers", "read:accounts", "read:transactions", "read:risk_flags", "read:audit_logs", "read:pii"],
            "admin":      ["read:customers", "read:accounts", "read:transactions", "read:risk_flags", "read:audit_logs", "read:pii", "admin:users", "admin:roles", "write:reports"],
        }
        return User(
            user_id=user_id,
            user_role=user_role,
            permissions=ROLE_PERMISSIONS.get(user_role, [])
        )
        
    gw.app.dependency_overrides[get_current_user] = override_get_current_user
    
    yield client, tokens
    
    gw.app.dependency_overrides.pop(get_current_user, None)

def _h(token: str) -> dict:
    return {"Authorization": token}


# 1. Bcrypt login succeeds with correct password
def test_bcrypt_login_success(app_and_tokens):
    client, _ = app_and_tokens
    user_row = {
        "user_id": "admin_001",
        "role": "admin",
        "password_hash": "$2b$12$kc0bFMxOvWwy6Y6vd23VOeoWHSgBh3MPKUqlBiD2wmEG.nbuChW4y",
        "permissions": [],
        "status": "active",
        "must_change_password": False
    }
    # Direct authentication test, bypassing dependency overrides
    client.app.state.db = make_db(fetch_one_return=user_row, fetch_all_return=[])
    
    r = client.post("/auth/login", data={"username": "admin_001", "password": "password"})
    assert r.status_code == 200
    assert "access_token" in r.json()
    assert r.json()["user_role"] == "admin"


# 2. Bcrypt login fails with wrong password
def test_bcrypt_login_fail_wrong_password(app_and_tokens):
    client, _ = app_and_tokens
    user_row = {
        "user_id": "admin_001",
        "role": "admin",
        "password_hash": "$2b$12$kc0bFMxOvWwy6Y6vd23VOeoWHSgBh3MPKUqlBiD2wmEG.nbuChW4y",
        "permissions": [],
        "status": "active",
        "must_change_password": False
    }
    client.app.state.db = make_db(fetch_one_return=user_row, fetch_all_return=[])
    
    r = client.post("/auth/login", data={"username": "admin_001", "password": "wrongpassword"})
    assert r.status_code == 401
    assert r.json()["detail"]["error"] == "AUTH_FAILED"


# 3. Inactive/suspended user cannot login
def test_suspended_user_login_fail(app_and_tokens):
    client, _ = app_and_tokens
    user_row = {
        "user_id": "analyst_001",
        "role": "analyst",
        "password_hash": "$2b$12$kc0bFMxOvWwy6Y6vd23VOeoWHSgBh3MPKUqlBiD2wmEG.nbuChW4y",
        "permissions": [],
        "status": "suspended",
        "must_change_password": False
    }
    client.app.state.db = make_db(fetch_one_return=user_row, fetch_all_return=[])
    
    r = client.post("/auth/login", data={"username": "analyst_001", "password": "password"})
    assert r.status_code == 401


# 4. Admin can create a new user
def test_admin_create_user_success(app_and_tokens):
    client, tokens = app_and_tokens
    db = make_db()
    db.fetch_one = AsyncMock(side_effect=[
        {"role_id": "analyst"}, # role exists check
        None, # existing user_id or email check
    ])
    client.app.state.db = db
    
    payload = {
        "user_id": "new_analyst",
        "email": "new_analyst@bankintel.hq",
        "name": "New Analyst",
        "role": "analyst",
        "bank_id": "hq_main"
    }
    r = client.post("/admin/users", json=payload, headers=_h(tokens["admin"]))
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == "new_analyst"
    assert "temp_password" in body
    assert body["must_change_password"] is True
    assert db.execute.call_count >= 2


# 5. Non-admin cannot create a user (403)
def test_non_admin_cannot_create_user(app_and_tokens):
    client, tokens = app_and_tokens
    payload = {
        "user_id": "new_analyst",
        "email": "new_analyst@bankintel.hq",
        "name": "New Analyst",
        "role": "analyst",
        "bank_id": "hq_main"
    }
    r = client.post("/admin/users", json=payload, headers=_h(tokens["analyst"]))
    assert r.status_code == 403


# 6. Role assignment changes are reflected on next login
def test_role_change_reflected_on_login(app_and_tokens):
    client, _ = app_and_tokens
    user_row = {
        "user_id": "analyst_001",
        "role": "compliance",
        "password_hash": "$2b$12$kc0bFMxOvWwy6Y6vd23VOeoWHSgBh3MPKUqlBiD2wmEG.nbuChW4y",
        "permissions": [],
        "status": "active",
        "must_change_password": False
    }
    role_perms = [{"permission_key": "read:audit_logs"}, {"permission_key": "read:pii"}]
    db = make_db()
    db.fetch_one = AsyncMock(return_value=user_row)
    db.fetch_all = AsyncMock(return_value=role_perms)
    client.app.state.db = db
    
    r = client.post("/auth/login", data={"username": "analyst_001", "password": "password"})
    assert r.status_code == 200
    assert r.json()["user_role"] == "compliance"


# 7. Last admin cannot be suspended (400)
def test_last_admin_cannot_be_suspended(app_and_tokens):
    client, tokens = app_and_tokens
    db = make_db()
    db.fetch_one = AsyncMock(side_effect=[
        {"role": "admin", "status": "active"}, # target user row
        {"role": "admin", "status": "active"}, # _is_last_active_admin select
        {"count": 1}, # count active admins
    ])
    client.app.state.db = db
    
    r = client.patch("/admin/users/admin_001/status", json={"status": "suspended"}, headers=_h(tokens["admin"]))
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "LAST_ADMIN_SAFEGUARD"


# 8. Last admin role cannot be changed away from admin (400)
def test_last_admin_role_cannot_be_changed(app_and_tokens):
    client, tokens = app_and_tokens
    db = make_db()
    db.fetch_one = AsyncMock(side_effect=[
        {"role": "admin", "status": "active"}, # target user row
        {"role_id": "analyst"}, # new role exists check
        {"role": "admin", "status": "active"}, # _is_last_active_admin select
        {"count": 1}, # count active admins
    ])
    client.app.state.db = db
    
    r = client.patch("/admin/users/admin_001/roles", json={"role": "analyst"}, headers=_h(tokens["admin"]))
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "LAST_ADMIN_SAFEGUARD"


# 9. user_activity_log receives entry for every admin write
def test_admin_write_logs_activity(app_and_tokens):
    client, tokens = app_and_tokens
    db = make_db()
    db.fetch_one = AsyncMock(side_effect=[
        {"role_id": "analyst"},
        None,
    ])
    client.app.state.db = db
    payload = {
        "user_id": "new_user",
        "email": "new_user@bankintel.hq",
        "name": "New User",
        "role": "analyst",
        "bank_id": "hq_main"
    }
    r = client.post("/admin/users", json=payload, headers=_h(tokens["admin"]))
    assert r.status_code == 200
    
    calls = db.execute.call_args_list
    assert any("INSERT INTO user_activity_log" in call[0][0] for call in calls)


# 10. Unique email constraint returns 409
def test_create_user_email_conflict(app_and_tokens):
    client, tokens = app_and_tokens
    db = make_db()
    db.fetch_one = AsyncMock(side_effect=[
        {"role_id": "analyst"}, # role exists check
        {"user_id": "other_user", "email": "conflict@bankintel.hq"}, # conflict check
    ])
    client.app.state.db = db
    
    payload = {
        "user_id": "new_user",
        "email": "conflict@bankintel.hq",
        "name": "New User",
        "role": "analyst",
        "bank_id": "hq_main"
    }
    r = client.post("/admin/users", json=payload, headers=_h(tokens["admin"]))
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "USER_ALREADY_EXISTS"


# 11. Password is never returned in any response
def test_password_never_returned_in_responses(app_and_tokens):
    client, tokens = app_and_tokens
    user_row = {
        "user_id": "analyst_001",
        "email": "analyst_001@bankintel.hq",
        "name": "Analyst One",
        "role": "analyst",
        "bank_id": "hq_main",
        "created_at": datetime.utcnow(),
        "last_login": datetime.utcnow(),
        "status": "active"
    }
    client.app.state.db = make_db(fetch_one_return=user_row)
    
    r = client.get("/admin/users/analyst_001", headers=_h(tokens["admin"]))
    assert r.status_code == 200
    body = r.json()
    assert "password" not in body
    assert "password_hash" not in body
