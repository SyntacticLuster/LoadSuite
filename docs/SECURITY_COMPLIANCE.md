# Security & Compliance

## FreightLens Security Architecture & Compliance Framework

**Version:** 1.0  
**Last Updated:** 2024-12-19  
**Classification:** Internal

---

## Overview

FreightLens handles sensitive business data including load pricing, broker financials, carrier operations, and user preferences. This document defines the security controls, compliance requirements, and data protection measures.

### Security Objectives

| Objective | Description |
|-----------|-------------|
| **Confidentiality** | Protect proprietary rate data, user preferences, and business intelligence |
| **Integrity** | Ensure accuracy of scoring, broker ratings, and load information |
| **Availability** | Maintain 99.9% uptime SLA for load discovery operations |
| **Accountability** | Full audit trail for all data access and modifications |

### Compliance Scope

| Framework | Applicability | Status |
|-----------|---------------|--------|
| SOC 2 Type II | User data, system security | Target: Phase 7 |
| GDPR | EU user data (if applicable) | Designed for compliance |
| CCPA | California user data | Designed for compliance |
| FMCSA Regulations | Carrier/broker data handling | Informational use |
| PCI DSS | Payment processing (future) | Out of scope (Phase 8+) |

---

## Authentication & Authorization

### Authentication Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         AUTHENTICATION FLOW                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────┐      ┌──────────────┐      ┌──────────────┐              │
│  │  Client  │─────▶│   API GW     │─────▶│  Auth Service│              │
│  └──────────┘      └──────────────┘      └──────────────┘              │
│       │                   │                     │                       │
│       │                   │                     ▼                       │
│       │                   │              ┌──────────────┐              │
│       │                   │              │  Identity DB │              │
│       │                   │              └──────────────┘              │
│       │                   │                     │                       │
│       │                   ▼                     ▼                       │
│       │           ┌──────────────┐      ┌──────────────┐              │
│       │           │ JWT Validation│◀────│ Token Store  │              │
│       │           └──────────────┘      └──────────────┘              │
│       │                   │                                            │
│       ▼                   ▼                                            │
│  ┌──────────────────────────────────────┐                              │
│  │            Protected Resources        │                              │
│  │  /api/loads  /api/preferences  etc.  │                              │
│  └──────────────────────────────────────┘                              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Authentication Methods

#### JWT Token Authentication (Primary)

```python
# app/auth/jwt.py
from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
from pydantic import BaseModel

class TokenPayload(BaseModel):
    sub: str  # user_id
    email: str
    roles: list[str]
    iat: datetime
    exp: datetime
    jti: str  # JWT ID for revocation

class JWTConfig:
    ALGORITHM = "RS256"  # RSA asymmetric for production
    ACCESS_TOKEN_EXPIRE_MINUTES = 60
    REFRESH_TOKEN_EXPIRE_DAYS = 30
    ISSUER = "freightlens"
    AUDIENCE = "freightlens-api"

def create_access_token(
    user_id: str,
    email: str,
    roles: list[str],
    private_key: str,
) -> str:
    """Create a signed JWT access token."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "roles": roles,
        "iat": now,
        "exp": now + timedelta(minutes=JWTConfig.ACCESS_TOKEN_EXPIRE_MINUTES),
        "jti": str(uuid.uuid4()),
        "iss": JWTConfig.ISSUER,
        "aud": JWTConfig.AUDIENCE,
    }
    return jwt.encode(payload, private_key, algorithm=JWTConfig.ALGORITHM)

def verify_access_token(token: str, public_key: str) -> TokenPayload:
    """Verify and decode a JWT access token."""
    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=[JWTConfig.ALGORITHM],
            issuer=JWTConfig.ISSUER,
            audience=JWTConfig.AUDIENCE,
        )
        return TokenPayload(**payload)
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise AuthenticationError(f"Invalid token: {e}")
```

#### API Key Authentication (Service-to-Service)

```python
# app/auth/api_key.py
from hashlib import sha256
from secrets import compare_digest

class APIKeyAuth:
    """API key authentication for service-to-service calls."""
    
    PREFIX = "rb_"  # FreightLens prefix
    
    @staticmethod
    def generate_key() -> tuple[str, str]:
        """Generate a new API key and its hash."""
        raw_key = f"{APIKeyAuth.PREFIX}{secrets.token_urlsafe(32)}"
        key_hash = sha256(raw_key.encode()).hexdigest()
        return raw_key, key_hash
    
    @staticmethod
    def verify_key(provided_key: str, stored_hash: str) -> bool:
        """Verify an API key against its stored hash."""
        provided_hash = sha256(provided_key.encode()).hexdigest()
        return compare_digest(provided_hash, stored_hash)
```

#### OAuth 2.0 / OIDC (Future)

Planned integration with identity providers:

| Provider | Use Case |
|----------|----------|
| Google Workspace | Enterprise SSO |
| Microsoft Entra ID | Enterprise SSO |
| Okta | Enterprise SSO |
| Auth0 | Consumer authentication |

### Authorization Model

#### Role-Based Access Control (RBAC)

```python
# app/auth/rbac.py
from enum import Enum
from typing import Set

class Permission(str, Enum):
    # Load operations
    LOADS_READ = "loads:read"
    LOADS_EXPORT = "loads:export"
    
    # Preference operations
    PREFERENCES_READ = "preferences:read"
    PREFERENCES_WRITE = "preferences:write"
    
    # Watchlist operations
    WATCHLISTS_READ = "watchlists:read"
    WATCHLISTS_WRITE = "watchlists:write"
    
    # Alert operations
    ALERTS_READ = "alerts:read"
    ALERTS_WRITE = "alerts:write"
    
    # Portfolio operations
    PORTFOLIO_READ = "portfolio:read"
    PORTFOLIO_WRITE = "portfolio:write"
    
    # Analytics
    ANALYTICS_READ = "analytics:read"
    ANALYTICS_EXPORT = "analytics:export"
    
    # Broker intelligence
    BROKERS_READ = "brokers:read"
    BROKERS_WRITE = "brokers:write"  # For ratings/reviews
    
    # Admin operations
    ADMIN_USERS = "admin:users"
    ADMIN_SYSTEM = "admin:system"
    ADMIN_AUDIT = "admin:audit"

class Role(str, Enum):
    ANONYMOUS = "anonymous"
    FREE_USER = "free_user"
    PRO_USER = "pro_user"
    FLEET_MANAGER = "fleet_manager"
    ENTERPRISE_USER = "enterprise_user"
    ADMIN = "admin"

# Role → Permission mapping
ROLE_PERMISSIONS: dict[Role, Set[Permission]] = {
    Role.ANONYMOUS: {
        Permission.LOADS_READ,
    },
    Role.FREE_USER: {
        Permission.LOADS_READ,
        Permission.PREFERENCES_READ,
        Permission.PREFERENCES_WRITE,
        Permission.WATCHLISTS_READ,
        Permission.WATCHLISTS_WRITE,
    },
    Role.PRO_USER: {
        Permission.LOADS_READ,
        Permission.LOADS_EXPORT,
        Permission.PREFERENCES_READ,
        Permission.PREFERENCES_WRITE,
        Permission.WATCHLISTS_READ,
        Permission.WATCHLISTS_WRITE,
        Permission.ALERTS_READ,
        Permission.ALERTS_WRITE,
        Permission.ANALYTICS_READ,
        Permission.BROKERS_READ,
        Permission.BROKERS_WRITE,
    },
    Role.FLEET_MANAGER: {
        # All PRO permissions plus...
        Permission.PORTFOLIO_READ,
        Permission.PORTFOLIO_WRITE,
        Permission.ANALYTICS_EXPORT,
    },
    Role.ENTERPRISE_USER: {
        # All FLEET_MANAGER permissions plus team features
    },
    Role.ADMIN: {
        # All permissions
        *Permission,
    },
}

def has_permission(roles: list[str], permission: Permission) -> bool:
    """Check if any role grants the required permission."""
    for role_name in roles:
        try:
            role = Role(role_name)
            if permission in ROLE_PERMISSIONS.get(role, set()):
                return True
        except ValueError:
            continue
    return False
```

#### Resource-Level Authorization

```python
# app/auth/resource_auth.py
from fastapi import Depends, HTTPException, status

async def authorize_watchlist_access(
    watchlist_id: str,
    current_user: User = Depends(get_current_user),
    watchlist_repo: WatchlistRepository = Depends(),
) -> Watchlist:
    """Verify user owns or has access to the watchlist."""
    watchlist = await watchlist_repo.get(watchlist_id)
    
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    
    # Owner check
    if watchlist.owner_id == current_user.id:
        return watchlist
    
    # Team member check (for shared watchlists)
    if current_user.id in watchlist.shared_with:
        return watchlist
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized to access this watchlist"
    )
```

### Session Management

```python
# app/auth/session.py
from datetime import datetime, timedelta
import redis.asyncio as redis

class SessionManager:
    """Manage user sessions and token revocation."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.prefix = "session:"
        self.revoked_prefix = "revoked:"
    
    async def create_session(
        self,
        user_id: str,
        jti: str,
        device_info: dict,
        expires_in: timedelta,
    ) -> None:
        """Create a new session entry."""
        session_key = f"{self.prefix}{user_id}:{jti}"
        session_data = {
            "user_id": user_id,
            "jti": jti,
            "device": device_info.get("device_type"),
            "ip": device_info.get("ip_address"),
            "user_agent": device_info.get("user_agent"),
            "created_at": datetime.utcnow().isoformat(),
        }
        await self.redis.hset(session_key, mapping=session_data)
        await self.redis.expire(session_key, expires_in)
    
    async def revoke_token(self, jti: str, expires_at: datetime) -> None:
        """Add token to revocation list."""
        revoked_key = f"{self.revoked_prefix}{jti}"
        ttl = int((expires_at - datetime.utcnow()).total_seconds())
        if ttl > 0:
            await self.redis.set(revoked_key, "1", ex=ttl)
    
    async def is_token_revoked(self, jti: str) -> bool:
        """Check if token has been revoked."""
        return await self.redis.exists(f"{self.revoked_prefix}{jti}")
    
    async def revoke_all_user_sessions(self, user_id: str) -> int:
        """Revoke all sessions for a user (e.g., password change)."""
        pattern = f"{self.prefix}{user_id}:*"
        count = 0
        async for key in self.redis.scan_iter(pattern):
            session = await self.redis.hgetall(key)
            if session:
                jti = session.get("jti")
                # Add to revocation list
                await self.redis.set(
                    f"{self.revoked_prefix}{jti}",
                    "1",
                    ex=86400  # 24 hours
                )
                await self.redis.delete(key)
                count += 1
        return count
```

### Password Policy

```python
# app/auth/password.py
import re
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

class PasswordPolicy:
    MIN_LENGTH = 12
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_DIGIT = True
    REQUIRE_SPECIAL = True
    SPECIAL_CHARS = r"!@#$%^&*()_+-=[]{}|;':\",./<>?"
    
    # Breached password check (via k-anonymity API)
    CHECK_BREACHED = True
    
    @classmethod
    def validate(cls, password: str) -> list[str]:
        """Validate password against policy. Returns list of violations."""
        violations = []
        
        if len(password) < cls.MIN_LENGTH:
            violations.append(f"Password must be at least {cls.MIN_LENGTH} characters")
        
        if cls.REQUIRE_UPPERCASE and not re.search(r"[A-Z]", password):
            violations.append("Password must contain at least one uppercase letter")
        
        if cls.REQUIRE_LOWERCASE and not re.search(r"[a-z]", password):
            violations.append("Password must contain at least one lowercase letter")
        
        if cls.REQUIRE_DIGIT and not re.search(r"\d", password):
            violations.append("Password must contain at least one digit")
        
        if cls.REQUIRE_SPECIAL and not re.search(f"[{re.escape(cls.SPECIAL_CHARS)}]", password):
            violations.append("Password must contain at least one special character")
        
        return violations

class PasswordHasher:
    """Secure password hashing using Argon2id."""
    
    def __init__(self):
        self.hasher = PasswordHasher(
            time_cost=3,        # iterations
            memory_cost=65536,  # 64 MB
            parallelism=4,      # threads
            hash_len=32,        # output length
            salt_len=16,        # salt length
        )
    
    def hash(self, password: str) -> str:
        """Hash a password."""
        return self.hasher.hash(password)
    
    def verify(self, hash: str, password: str) -> bool:
        """Verify a password against its hash."""
        try:
            self.hasher.verify(hash, password)
            return True
        except VerifyMismatchError:
            return False
    
    def needs_rehash(self, hash: str) -> bool:
        """Check if hash needs to be upgraded."""
        return self.hasher.check_needs_rehash(hash)
```

### Multi-Factor Authentication (MFA)

```python
# app/auth/mfa.py
import pyotp
from enum import Enum

class MFAMethod(str, Enum):
    TOTP = "totp"          # Time-based OTP (Google Authenticator)
    SMS = "sms"            # SMS verification
    EMAIL = "email"        # Email verification
    WEBAUTHN = "webauthn"  # Hardware keys / biometrics

class TOTPManager:
    """TOTP-based MFA management."""
    
    ISSUER = "FreightLens"
    DIGITS = 6
    INTERVAL = 30  # seconds
    
    @classmethod
    def generate_secret(cls) -> str:
        """Generate a new TOTP secret."""
        return pyotp.random_base32()
    
    @classmethod
    def get_provisioning_uri(cls, secret: str, email: str) -> str:
        """Generate provisioning URI for authenticator apps."""
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(name=email, issuer_name=cls.ISSUER)
    
    @classmethod
    def verify_code(cls, secret: str, code: str) -> bool:
        """Verify a TOTP code."""
        totp = pyotp.TOTP(secret)
        # Allow 1 period tolerance for clock skew
        return totp.verify(code, valid_window=1)
```

---

## Audit Logging

### Audit Event Schema

```python
# app/audit/models.py
from datetime import datetime
from enum import Enum
from pydantic import BaseModel
from typing import Optional, Any

class AuditAction(str, Enum):
    # Authentication
    AUTH_LOGIN_SUCCESS = "auth.login.success"
    AUTH_LOGIN_FAILURE = "auth.login.failure"
    AUTH_LOGOUT = "auth.logout"
    AUTH_PASSWORD_CHANGE = "auth.password.change"
    AUTH_MFA_ENABLE = "auth.mfa.enable"
    AUTH_MFA_DISABLE = "auth.mfa.disable"
    AUTH_SESSION_REVOKE = "auth.session.revoke"
    
    # User management
    USER_CREATE = "user.create"
    USER_UPDATE = "user.update"
    USER_DELETE = "user.delete"
    USER_ROLE_CHANGE = "user.role.change"
    
    # Data access
    DATA_LOADS_VIEW = "data.loads.view"
    DATA_LOADS_EXPORT = "data.loads.export"
    DATA_BROKER_VIEW = "data.broker.view"
    DATA_ANALYTICS_VIEW = "data.analytics.view"
    
    # Preferences
    PREF_UPDATE = "preferences.update"
    
    # Watchlists
    WATCHLIST_CREATE = "watchlist.create"
    WATCHLIST_UPDATE = "watchlist.update"
    WATCHLIST_DELETE = "watchlist.delete"
    WATCHLIST_SHARE = "watchlist.share"
    
    # Alerts
    ALERT_CREATE = "alert.create"
    ALERT_UPDATE = "alert.update"
    ALERT_DELETE = "alert.delete"
    ALERT_TRIGGER = "alert.trigger"
    
    # Portfolio
    PORTFOLIO_TRUCK_ADD = "portfolio.truck.add"
    PORTFOLIO_TRUCK_UPDATE = "portfolio.truck.update"
    PORTFOLIO_TRUCK_REMOVE = "portfolio.truck.remove"
    
    # Admin
    ADMIN_CONFIG_CHANGE = "admin.config.change"
    ADMIN_USER_IMPERSONATE = "admin.user.impersonate"
    ADMIN_DATA_EXPORT = "admin.data.export"

class AuditEvent(BaseModel):
    """Immutable audit log entry."""
    
    id: str                          # Unique event ID
    timestamp: datetime              # Event timestamp (UTC)
    action: AuditAction              # Action type
    actor_id: Optional[str]          # User ID (null for system events)
    actor_email: Optional[str]       # User email
    actor_ip: Optional[str]          # Client IP address
    actor_user_agent: Optional[str]  # Client user agent
    
    resource_type: Optional[str]     # Type of resource affected
    resource_id: Optional[str]       # ID of resource affected
    
    request_id: Optional[str]        # Correlation with request logs
    trace_id: Optional[str]          # Distributed trace ID
    
    outcome: str                     # success | failure
    reason: Optional[str]            # Failure reason if applicable
    
    metadata: dict[str, Any] = {}    # Additional context
    
    # Integrity
    previous_hash: Optional[str]     # Hash of previous event (chain)
    event_hash: str                  # Hash of this event
```

### Audit Logger Implementation

```python
# app/audit/logger.py
import hashlib
import json
from datetime import datetime, timezone

class AuditLogger:
    """Write-once audit logger with tamper detection."""
    
    def __init__(self, store: AuditStore):
        self.store = store
        self._last_hash: Optional[str] = None
    
    def _compute_hash(self, event: dict) -> str:
        """Compute SHA-256 hash of event data."""
        # Exclude event_hash from computation
        hashable = {k: v for k, v in event.items() if k != "event_hash"}
        canonical = json.dumps(hashable, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()
    
    async def log(
        self,
        action: AuditAction,
        actor: Optional[User],
        request_context: Optional[RequestContext],
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        outcome: str = "success",
        reason: Optional[str] = None,
        metadata: dict = None,
    ) -> AuditEvent:
        """Record an audit event."""
        
        event_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)
        
        # Build event
        event_data = {
            "id": event_id,
            "timestamp": timestamp.isoformat(),
            "action": action.value,
            "actor_id": actor.id if actor else None,
            "actor_email": actor.email if actor else None,
            "actor_ip": request_context.client_ip if request_context else None,
            "actor_user_agent": request_context.user_agent if request_context else None,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "request_id": request_context.request_id if request_context else None,
            "trace_id": request_context.trace_id if request_context else None,
            "outcome": outcome,
            "reason": reason,
            "metadata": metadata or {},
            "previous_hash": self._last_hash,
        }
        
        # Compute integrity hash
        event_data["event_hash"] = self._compute_hash(event_data)
        
        # Store event
        event = AuditEvent(**event_data)
        await self.store.append(event)
        
        # Update chain
        self._last_hash = event_data["event_hash"]
        
        return event
    
    async def verify_chain(self, start_id: str, end_id: str) -> bool:
        """Verify integrity of audit chain between two events."""
        events = await self.store.get_range(start_id, end_id)
        
        for i, event in enumerate(events):
            # Verify event hash
            computed = self._compute_hash(event.dict())
            if computed != event.event_hash:
                return False
            
            # Verify chain (except first event)
            if i > 0:
                if event.previous_hash != events[i-1].event_hash:
                    return False
        
        return True
```

### Audit Storage

```python
# app/audit/store.py
from abc import ABC, abstractmethod

class AuditStore(ABC):
    """Abstract audit storage interface."""
    
    @abstractmethod
    async def append(self, event: AuditEvent) -> None:
        """Append event to audit log (write-once)."""
        pass
    
    @abstractmethod
    async def get(self, event_id: str) -> Optional[AuditEvent]:
        """Retrieve a specific event."""
        pass
    
    @abstractmethod
    async def query(
        self,
        actor_id: Optional[str] = None,
        action: Optional[AuditAction] = None,
        resource_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """Query audit events."""
        pass

class PostgresAuditStore(AuditStore):
    """PostgreSQL-backed audit store with append-only table."""
    
    async def append(self, event: AuditEvent) -> None:
        # Insert-only table with no UPDATE/DELETE permissions
        await self.db.execute(
            """
            INSERT INTO audit_events (
                id, timestamp, action, actor_id, actor_email,
                actor_ip, actor_user_agent, resource_type, resource_id,
                request_id, trace_id, outcome, reason, metadata,
                previous_hash, event_hash
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
            """,
            event.id, event.timestamp, event.action, ...
        )

class S3AuditStore(AuditStore):
    """S3-backed audit store for long-term retention."""
    
    async def append(self, event: AuditEvent) -> None:
        # Write to S3 with Object Lock (WORM)
        key = f"audit/{event.timestamp.year}/{event.timestamp.month:02d}/{event.id}.json"
        await self.s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=event.json(),
            ObjectLockMode="GOVERNANCE",
            ObjectLockRetainUntilDate=event.timestamp + timedelta(days=365 * 7),
        )
```

### Audit Queries (Admin UI)

```sql
-- Recent failed login attempts
SELECT * FROM audit_events
WHERE action = 'auth.login.failure'
  AND timestamp > NOW() - INTERVAL '1 hour'
ORDER BY timestamp DESC;

-- User activity
SELECT * FROM audit_events
WHERE actor_id = 'user-123'
  AND timestamp > NOW() - INTERVAL '30 days'
ORDER BY timestamp DESC;

-- Data exports
SELECT * FROM audit_events
WHERE action IN ('data.loads.export', 'data.analytics.export', 'admin.data.export')
ORDER BY timestamp DESC;

-- Admin actions
SELECT * FROM audit_events
WHERE action LIKE 'admin.%'
ORDER BY timestamp DESC;
```

---

## Personal Data Protection

### Data Classification

| Classification | Description | Examples | Handling |
|----------------|-------------|----------|----------|
| **Public** | Non-sensitive business data | Load postings, equipment types | Standard handling |
| **Internal** | Business-sensitive | Rate analytics, market data | Access control, encryption at rest |
| **Confidential** | User/business secrets | Preferences, watchlists | Encryption, audit logging |
| **Restricted** | PII, credentials | Email, password hashes | Encryption, minimization, consent |

### PII Inventory

| Data Element | Classification | Purpose | Retention | Legal Basis |
|--------------|----------------|---------|-----------|-------------|
| Email address | Restricted | Account, notifications | Account lifetime + 30 days | Contract |
| Name | Confidential | Display, invoicing | Account lifetime + 7 years | Contract |
| Phone number | Restricted | SMS alerts, support | Account lifetime + 30 days | Consent |
| IP address | Restricted | Security, fraud prevention | 90 days | Legitimate interest |
| Device info | Confidential | Session management | 90 days | Legitimate interest |
| Location (truck) | Confidential | Recommendations | Real-time only | Consent |
| Payment info | Restricted | Billing (future) | Account lifetime + 7 years | Contract |
| MC/DOT numbers | Internal | Carrier identification | Indefinite | Public record |

### Data Minimization

```python
# app/privacy/minimization.py

class DataMinimizer:
    """Apply data minimization principles."""
    
    @staticmethod
    def for_logging(user: User) -> dict:
        """Return only necessary fields for logging."""
        return {
            "user_id": user.id,
            # Email truncated for logs
            "email_domain": user.email.split("@")[1] if user.email else None,
        }
    
    @staticmethod
    def for_analytics(user: User) -> dict:
        """Return anonymized data for analytics."""
        return {
            "user_id_hash": hashlib.sha256(user.id.encode()).hexdigest()[:16],
            "account_age_days": (datetime.utcnow() - user.created_at).days,
            "tier": user.subscription_tier,
            "region": user.region,  # Coarse location only
        }
    
    @staticmethod
    def for_export(user: User) -> dict:
        """Return all user data for GDPR export."""
        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "phone": user.phone,
            "created_at": user.created_at.isoformat(),
            "preferences": user.preferences,
            "watchlists": [...],
            "alerts": [...],
        }
```

### Right to Access (GDPR Article 15)

```python
# app/privacy/access.py

@router.get("/api/privacy/my-data")
async def export_my_data(
    current_user: User = Depends(get_current_user),
    audit: AuditLogger = Depends(),
) -> DataExportResponse:
    """Export all personal data for the current user."""
    
    # Collect all user data
    data = {
        "user_profile": await get_user_profile(current_user.id),
        "preferences": await get_preferences(current_user.id),
        "watchlists": await get_watchlists(current_user.id),
        "alerts": await get_alerts(current_user.id),
        "trucks": await get_trucks(current_user.id),
        "activity_log": await get_audit_events(actor_id=current_user.id),
    }
    
    # Audit the export
    await audit.log(
        action=AuditAction.DATA_LOADS_EXPORT,
        actor=current_user,
        resource_type="user_data",
        resource_id=current_user.id,
        metadata={"export_type": "gdpr_access"},
    )
    
    return DataExportResponse(
        generated_at=datetime.utcnow(),
        data=data,
    )
```

### Right to Erasure (GDPR Article 17)

```python
# app/privacy/erasure.py

@router.delete("/api/privacy/my-data")
async def delete_my_data(
    confirmation: DeleteConfirmation,
    current_user: User = Depends(get_current_user),
    audit: AuditLogger = Depends(),
) -> DeletionResponse:
    """Delete all personal data (Right to Erasure)."""
    
    if confirmation.confirm_text != "DELETE MY DATA":
        raise HTTPException(400, "Confirmation text does not match")
    
    # Pre-deletion audit (will be retained)
    await audit.log(
        action=AuditAction.USER_DELETE,
        actor=current_user,
        resource_type="user",
        resource_id=current_user.id,
        metadata={"reason": confirmation.reason},
    )
    
    # Delete user data
    deleted = await privacy_service.delete_user_data(
        user_id=current_user.id,
        retain_audit=True,  # Audit logs retained for legal compliance
    )
    
    # Revoke all sessions
    await session_manager.revoke_all_user_sessions(current_user.id)
    
    return DeletionResponse(
        status="completed",
        deleted_items=deleted,
        retention_note="Audit logs retained for 7 years per legal requirements",
    )
```

### Consent Management

```python
# app/privacy/consent.py
from enum import Enum

class ConsentPurpose(str, Enum):
    ESSENTIAL = "essential"           # Required for service
    ANALYTICS = "analytics"           # Usage analytics
    MARKETING = "marketing"           # Marketing communications
    THIRD_PARTY = "third_party"       # Sharing with partners
    LOCATION = "location"             # Real-time location tracking

class ConsentRecord(BaseModel):
    user_id: str
    purpose: ConsentPurpose
    granted: bool
    timestamp: datetime
    ip_address: str
    version: str  # Consent policy version

class ConsentManager:
    """Manage user consent preferences."""
    
    async def get_consents(self, user_id: str) -> dict[ConsentPurpose, bool]:
        """Get all consent preferences for a user."""
        records = await self.store.get_latest_consents(user_id)
        return {r.purpose: r.granted for r in records}
    
    async def update_consent(
        self,
        user_id: str,
        purpose: ConsentPurpose,
        granted: bool,
        ip_address: str,
    ) -> ConsentRecord:
        """Record a consent decision."""
        record = ConsentRecord(
            user_id=user_id,
            purpose=purpose,
            granted=granted,
            timestamp=datetime.utcnow(),
            ip_address=ip_address,
            version=CONSENT_POLICY_VERSION,
        )
        await self.store.save(record)
        return record
    
    def check_consent(self, user: User, purpose: ConsentPurpose) -> bool:
        """Check if user has granted consent for a purpose."""
        if purpose == ConsentPurpose.ESSENTIAL:
            return True  # Always allowed
        return user.consents.get(purpose, False)
```

---

## Data Encryption

### Encryption at Rest

| Layer | Encryption | Key Management |
|-------|------------|----------------|
| Database | AES-256-GCM (PostgreSQL TDE) | AWS KMS / HashiCorp Vault |
| File Storage | AES-256 (S3 SSE-KMS) | AWS KMS |
| Cache | AES-256 (Redis TLS) | Application-managed |
| Backups | AES-256-GCM | Offline key storage |

### Encryption in Transit

| Connection | Protocol | Minimum Version |
|------------|----------|-----------------|
| Client → API | TLS | 1.3 (1.2 fallback) |
| API → Database | TLS | 1.2 |
| API → Cache | TLS | 1.2 |
| API → External APIs | TLS | 1.2 |
| Internal services | mTLS | 1.3 |

### Field-Level Encryption

```python
# app/crypto/field_encryption.py
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

class FieldEncryptor:
    """Encrypt sensitive fields at the application layer."""
    
    def __init__(self, master_key: bytes):
        self.fernet = Fernet(master_key)
    
    def encrypt(self, plaintext: str) -> str:
        """Encrypt a string field."""
        return self.fernet.encrypt(plaintext.encode()).decode()
    
    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a string field."""
        return self.fernet.decrypt(ciphertext.encode()).decode()

# Fields requiring application-level encryption
ENCRYPTED_FIELDS = {
    "User": ["phone", "ssn_last4"],
    "APIKey": ["key_hash"],  # Double encryption
    "Webhook": ["secret"],
}
```

---

## API Security

### Rate Limiting

```python
# app/security/rate_limit.py
from fastapi import Request, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# Tier-based limits
RATE_LIMITS = {
    "anonymous": "30/minute",
    "free_user": "100/minute",
    "pro_user": "500/minute",
    "enterprise": "2000/minute",
}

@app.get("/api/loads")
@limiter.limit(lambda: get_user_rate_limit())
async def get_loads(request: Request):
    ...
```

### Input Validation

```python
# app/security/validation.py
from pydantic import BaseModel, validator, constr
import re

class LoadSearchQuery(BaseModel):
    q: constr(max_length=200) = None
    equipment: constr(max_length=50) = None
    rpm_min: float = None
    rpm_max: float = None
    
    @validator("q")
    def sanitize_query(cls, v):
        if v is None:
            return v
        # Remove potential injection patterns
        v = re.sub(r"[<>\"';]", "", v)
        return v.strip()
    
    @validator("rpm_min", "rpm_max")
    def validate_rate(cls, v):
        if v is not None and (v < 0 or v > 100):
            raise ValueError("Rate must be between 0 and 100")
        return v
```

### CORS Configuration

```python
# app/security/cors.py
from fastapi.middleware.cors import CORSMiddleware

ALLOWED_ORIGINS = [
    "https://freightlens.io",
    "https://app.freightlens.io",
    "https://staging.freightlens.io",
]

if settings.ENVIRONMENT == "development":
    ALLOWED_ORIGINS.append("http://localhost:3000")
    ALLOWED_ORIGINS.append("http://localhost:8035")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID", "X-RateLimit-Remaining"],
    max_age=600,  # Preflight cache
)
```

### Security Headers

```python
# app/security/headers.py
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        
        # Prevent MIME sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # XSS protection
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Strict Transport Security
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )
        
        # Content Security Policy
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' https://fonts.gstatic.com; "
            "connect-src 'self' https://api.freightlens.io; "
            "frame-ancestors 'none';"
        )
        
        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Permissions policy
        response.headers["Permissions-Policy"] = (
            "geolocation=(self), microphone=(), camera=()"
        )
        
        return response
```

---

## Vulnerability Management

### Dependency Scanning

```yaml
# .github/workflows/security.yml
name: Security Scan

on:
  push:
    branches: [main]
  pull_request:
  schedule:
    - cron: "0 0 * * *"  # Daily

jobs:
  dependency-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Run Snyk
        uses: snyk/actions/python@master
        with:
          args: --severity-threshold=high
        env:
          SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}
      
      - name: Run Safety
        run: |
          pip install safety
          safety check --full-report

  sast-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Run Bandit
        run: |
          pip install bandit
          bandit -r app/ -ll -ii
      
      - name: Run Semgrep
        uses: returntocorp/semgrep-action@v1
        with:
          config: p/python
```

### Container Scanning

```yaml
  container-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Build image
        run: docker build -t freightlens-api:scan .
      
      - name: Run Trivy
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: freightlens-api:scan
          format: table
          exit-code: 1
          severity: CRITICAL,HIGH
```

### Security Patching SLA

| Severity | Definition | Patch SLA |
|----------|------------|-----------|
| Critical | RCE, auth bypass, data breach | 24 hours |
| High | Privilege escalation, XSS | 7 days |
| Medium | Information disclosure | 30 days |
| Low | Best practice violations | 90 days |

---

## Licensing & Third-Party Data

### Software Licenses

| Component | License | Commercial Use |
|-----------|---------|----------------|
| FastAPI | MIT | ✓ Allowed |
| Pydantic | MIT | ✓ Allowed |
| Uvicorn | BSD-3 | ✓ Allowed |
| structlog | MIT | ✓ Allowed |
| httpx | BSD-3 | ✓ Allowed |
| OpenTelemetry | Apache-2.0 | ✓ Allowed |
| Prometheus client | Apache-2.0 | ✓ Allowed |

### Third-Party Data Sources

| Data Source | Terms | Attribution Required | Rate Limits |
|-------------|-------|---------------------|-------------|
| DAT Freight | Commercial API | Per contract | Per contract |
| Truckstop.com | Commercial API | Per contract | Per contract |
| FMCSA SAFER | Public (gov) | No | 10 req/sec |
| FreightWaves SONAR | Commercial API | Yes | Per contract |
| OpenStreetMap | ODbL | Yes | Fair use |
| HERE Maps | Commercial | Per contract | Per contract |

### Data Usage Restrictions

```python
# app/data/attribution.py

class DataSource(str, Enum):
    DAT = "dat"
    TRUCKSTOP = "truckstop"
    FMCSA = "fmcsa"
    FREIGHTWAVES = "freightwaves"
    INTERNAL = "internal"

DATA_USAGE_RULES = {
    DataSource.DAT: {
        "can_display": True,
        "can_export": False,  # Per contract
        "can_derive": True,
        "can_cache": True,
        "cache_ttl_hours": 1,
        "attribution": None,  # No public attribution required
    },
    DataSource.FMCSA: {
        "can_display": True,
        "can_export": True,
        "can_derive": True,
        "can_cache": True,
        "cache_ttl_hours": 24,
        "attribution": None,  # Public data
    },
    DataSource.FREIGHTWAVES: {
        "can_display": True,
        "can_export": False,
        "can_derive": True,
        "can_cache": True,
        "cache_ttl_hours": 4,
        "attribution": "Data provided by FreightWaves SONAR",
    },
}

def check_data_usage(source: DataSource, operation: str) -> bool:
    """Check if an operation is allowed for a data source."""
    rules = DATA_USAGE_RULES.get(source, {})
    return rules.get(f"can_{operation}", False)
```

### Open Source License Compliance

```bash
# Generate SBOM (Software Bill of Materials)
pip install pip-licenses
pip-licenses --format=json --output-file=sbom.json

# Check for GPL contamination
pip-licenses --fail-on="GPL;LGPL;AGPL"
```

---

## Incident Response

### Incident Classification

| Severity | Definition | Examples | Response Time |
|----------|------------|----------|---------------|
| P1 - Critical | Service down, data breach | Full outage, unauthorized access | 15 minutes |
| P2 - High | Major feature broken | Auth failure, data corruption | 1 hour |
| P3 - Medium | Feature degraded | Slow performance, partial failure | 4 hours |
| P4 - Low | Minor issue | UI bug, non-critical error | 24 hours |

### Security Incident Procedure

```
1. DETECT
   └─ Automated alerting, user report, security scan

2. CONTAIN
   ├─ Isolate affected systems
   ├─ Revoke compromised credentials
   └─ Block malicious IPs

3. INVESTIGATE
   ├─ Collect logs and traces
   ├─ Identify attack vector
   └─ Assess data exposure

4. ERADICATE
   ├─ Patch vulnerability
   ├─ Remove malware/backdoors
   └─ Rotate all secrets

5. RECOVER
   ├─ Restore from clean backup
   ├─ Validate system integrity
   └─ Resume normal operations

6. POST-MORTEM
   ├─ Document timeline
   ├─ Identify root cause
   └─ Implement preventive measures
```

### Breach Notification

| Stakeholder | Timeline | Method |
|-------------|----------|--------|
| Internal security team | Immediate | Slack, PagerDuty |
| Executive team | 4 hours | Email, call |
| Affected users | 72 hours (GDPR) | Email |
| Regulators | 72 hours (GDPR) | Formal notice |
| Public disclosure | As required | Blog, press |

---

## Compliance Checklist

### SOC 2 Type II Readiness

| Control | Status | Notes |
|---------|--------|-------|
| Access control policies | 🟡 In Progress | RBAC implemented |
| Encryption at rest | ✅ Complete | AES-256 |
| Encryption in transit | ✅ Complete | TLS 1.3 |
| Audit logging | ✅ Complete | Immutable logs |
| Vulnerability management | 🟡 In Progress | CI/CD scanning |
| Incident response | 🟡 In Progress | Procedure documented |
| Change management | 🔴 Not Started | Needs formal process |
| Vendor management | 🔴 Not Started | Needs assessment |

### GDPR Compliance

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| Lawful basis | ✅ Complete | Contract + consent |
| Data minimization | ✅ Complete | Field-level controls |
| Right to access | ✅ Complete | `/api/privacy/my-data` |
| Right to erasure | ✅ Complete | `/api/privacy/my-data` DELETE |
| Data portability | ✅ Complete | JSON export |
| Consent management | ✅ Complete | Granular consents |
| Breach notification | 🟡 In Progress | Process documented |
| DPO designation | 🔴 Not Started | Required if >10 employees |

---

## Security Contacts

| Role | Contact | Escalation |
|------|---------|------------|
| Security Lead | security@freightlens.io | Primary |
| On-Call Engineer | PagerDuty rotation | After-hours |
| Privacy Officer | privacy@freightlens.io | GDPR/data requests |
| Legal | legal@freightlens.io | Breach, compliance |

### Vulnerability Disclosure

```
To report a security vulnerability:

Email: security@freightlens.io
PGP Key: [Published on website]

We will:
- Acknowledge within 24 hours
- Provide status update within 7 days
- Credit researchers (with permission)
- Not pursue legal action for good-faith research
```
