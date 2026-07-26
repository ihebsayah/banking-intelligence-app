# Auth System Baseline

This is the AUTHORITATIVE auth system baseline based on VERIFIED source code with exact file:line references.

## Authentication & Authorisation System

### VERIFIED Source Files
| File | Purpose |
|------|---------|
| services/api_gateway/auth.py | JWT creation, verification, user authentication |
| services/api_gateway/routes.py:355-491 | Auth dependency, RBAC helpers |
| services/shared/config.py:57-63 | JWT settings |
| services/shared/models.py:14-18 | UserRole enum |
| frontend/src/api/client.ts | Axios JWT interceptor |
| init/02-users-kpis.sql | users, roles, permissions, role_permissions tables |

### Login Flow
- **Endpoint**: POST /auth/login (routes.py:527-565)
- **Request format**: Form data with username + password fields
- **Response format**: LoginResponse(access_token, token_type="bearer", user_id, user_role, expires_in)
- **Library**: PyJWT (import jwt)
- **Algorithm**: HS256 (config.py:62)
- **Secret**: env JWT_SECRET_KEY, default "change-this-in-production-do-not-use-in-prod" (config.py:58-60)

### JWT Token Structure (auth.py:115-121)
```python
{
    "sub": user_id,
    "role": user_role,
    "iat": int(now.timestamp()),
    "exp": expire_ts,  # now + JWT_EXPIRE_MINUTES minutes
    "jti": str(uuid.uuid4())
}
```

### VERIFIED Contradictions Resolved

1. JWT EXPIRY:
   - config.py:63: JWT_EXPIRE_MINUTES: int = Field(default=480, description="Token TTL in minutes (8 hours)")
   - auth.py:112: expire = now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
   - auth.py:129: expires_in = settings.JWT_EXPIRE_MINUTES * 60 (returns seconds)
   - LoginResponse.expires_in: int (seconds)
   - CONTRADICTION RESOLVED: 480 minutes = 8 hours. NOT 24 hours.

2. DEV_MODE BEHAVIOUR:
   - config.py:87: DEV_MODE: bool = Field(default=True)
   - auth.py:188-194: When db is None AND DEV_MODE is True -> fallback to mock store
   - auth.py:268-270: When DB query fails AND DEV_MODE is True -> fallback to mock store
   - auth.py:274-290: _authenticate_mock checks username in MOCK_USERS dict, verifies bcrypt password
   - CONTRADICTION RESOLVED: DEV_MODE does NOT allow any username. It falls back to MOCK_USERS when DB is unavailable. Mock users still require valid passwords.

3. MOCK USERS (auth.py:37-93):
   - 5 mock users: analyst_001, analyst_002, compliance_001, manager_001, admin_001
   - All share the same bcrypt password hash
   - Password for all: same hash "$2b$12$kc0bFMxOvWwy6Y6vd23VOeoWHSgBh3MPKUqlBiD2wmEG.nbuChW4y"

4. REFRESH TOKEN:
   - NO /auth/refresh endpoint exists in routes.py
   - NO refresh token is issued
   - CONTRADICTION RESOLVED: No refresh token support. Single access token only.

5. LOGOUT:
   - NO /auth/logout endpoint exists in routes.py
   - Frontend clears localStorage token on 401
   - CONTRADICTION RESOLVED: No server-side logout. Client-side only.

6. ISSUER/AUDIENCE VALIDATION:
   - auth.py:151-155: jwt.decode uses only token + secret + algorithm
   - No issuer or audience validation
   - CONTRADICTION RESOLVED: No iss/aud validation.

7. JTI:
   - auth.py:120: jti is generated (str(uuid.uuid4()))
   - auth.py:156-157: jti is NOT validated on decode
   - CONTRADICTION RESOLVED: jti is generated but not validated.

8. PASSWORD HASHING:
   - auth.py:26: CryptContext(schemes=["bcrypt"], deprecated="auto")
   - auth.py:28-30: hash_password uses bcrypt
   - auth.py:213,283: pwd_context.verify for validation

9. ROLE PERMISSIONS (Hybrid - DB + hardcoded):
   - routes.py:390-398: Loads role_permissions from DB junction table
   - routes.py:400-407: Loads custom user permissions from users.permissions column
   - routes.py:408: Merges: permissions = list(set(role_perms) | set(custom_perms))
   - routes.py:433-437: ROLE_GROUPS hardcoded dict (business, compliance, admin groups)
   - CONTRADICTION RESOLVED: Both DB-backed role_permissions AND hardcoded ROLE_GROUPS. Role check uses ROLE_GROUPS. Permission check uses DB-loaded permissions.

10. ROLE HIERARCHY:
    - UserRole enum: ANALYST, COMPLIANCE, MANAGER, ADMIN
    - ROLE_GROUPS (routes.py:433-437):
      - "business": {ANALYST, MANAGER, ADMIN}
      - "compliance": {COMPLIANCE, ADMIN}
      - "admin": {ADMIN}
    - No inheritance, just group membership check

11. FRONTEND TOKEN FLOW:
    - client.ts:4: BASE_URL = import.meta.env.VITE_API_URL ?? '/api'
    - client.ts:14: localStorage.getItem('auth_token')
    - client.ts:16: config.headers.Authorization = Bearer ${token}
    - client.ts:25-28: 401 -> clear localStorage + redirect to /login
    - No refresh token, no token expiry handling

### RBAC Enforcement
- require_roles(*roles) -> routes.py:440-459: checks user_role against ROLE_GROUPS
- require_permission(permission) -> routes.py:462-474: checks user.permissions list
- require_any_permission(*permissions) -> routes.py:477-491: checks any permission

### DB Authentication Path (auth.py:196-261)
1. Query users table for user_id
2. Verify bcrypt password hash
3. Check user status = "active"
4. Update last_login timestamp
5. Load role_permissions from junction table
6. Load custom user permissions from users.permissions column
7. Merge and return User object
