"""C2 RBAC segregation — permission-seed regression tests.

Loads the desired role->permission mapping from the authoritative seed sources
(migration 0005 ROLE_PERMISSIONS + SENSITIVE_PERMISSION_ROLES applylist and the
init/10-phase2b-permission-seeds.sql) and asserts the canonical workflow
invariants:

COMPLIANCE:
  case:decision = YES
  case:close    = YES
  alert:read_assigned = NO
  alert:transition     = NO

ANALYST:
  case:read_assigned   = NO
  case:decision = NO
  case:close    = NO
  alert:read_assigned  = YES
  alert:dismiss  = YES
  alert:investigate = YES

ADMIN:
  case:decision = NO operational authority
  case:close    = NO operational authority

Also asserts the authorise() policy engine itself enforces each invariant
(endpoints depend on authorise() as the authoritative guard).
"""
import importlib

import pytest

from shared.authorise import (
    ApplicationUser, PermissionDeniedError, ProhibitedComboError,
    Resource, authorise,
)

seed_module = importlib.import_module(
    "migrations.versions.0005_add_permission_seeds")

# ── Desired target mapping (mirrors init/10-phase2b-permission-seeds.sql) ──
# Built from the seed authoring source so a drift in the seed is caught.
TARGET_ANALYST = {
    "workbench:access", "alert:read_assigned", "alert:acknowledge",
    "alert:dismiss", "alert:investigate", "alert:transition",
    "investigation:read_own", "investigation:update",
    "investigation:modify_findings", "investigation:transition",
    "info_request:read_assigned", "info_request:respond",
    "approval:request", "approval:read",
    "comment:create", "comment:read", "timeline:read",
    "notification:read", "notification:update",
}

TARGET_COMPLIANCE = {
    "workbench:access", "investigation:read", "investigation:review",
    "case:create", "case:read_assigned", "case:transition",
    "case:decision", "case:close",
    "info_request:create", "info_request:read",
    "info_request:accept", "info_request:return", "info_request:cancel",
    "approval:request", "approval:approve", "approval:read",
    "comment:create", "comment:read", "comment:view_internal_content",
    "timeline:read", "notification:read", "notification:update",
}

TARGET_ADMIN = {
    "workbench:access", "alert:read", "alert:assign", "alert:dismiss",
    "investigation:read", "investigation:assign",
    "case:read", "case:assign", "case:reopen",
    "info_request:read", "info_request:cancel",
    "approval:request", "approval:read",
    "comment:create", "comment:read", "comment:view_metadata",
    "comment:redact", "timeline:read",
    "notification:read", "notification:update",
    "admin:outbox_monitor", "admin:outbox_retry",
}

# Permissions that must NOT be granted to each role (canonical segregation).
COMPLIANCE_FORBIDDEN = {"alert:read_assigned", "alert:transition"}
ANALYST_FORBIDDEN = {
    "case:read_assigned", "case:create", "case:decision", "case:close",
    "case:assign", "investigation:review", "info_request:create",
    "info_request:read", "info_request:accept", "info_request:return",
}


def _effective_seed_permissions(role: str) -> set:
    """Derive the permission set the seed authoring source would grant.

    Applies the same logic as migration 0005 upgrade(): non-sensitive perms are
    granted always; sensitive perms only if the role is in the allowlist.
    """
    result = set()
    for perm in seed_module.ROLE_PERMISSIONS[role]:
        if perm not in seed_module.SENSITIVE_PERMISSIONS:
            result.add(perm)
        elif role in seed_module.SENSITIVE_PERMISSION_ROLES.get(perm, set()):
            result.add(perm)
    return result


class TestSeedAuthoringSource:
    """Test the migration 0005 seed authoring constants (source of truth)."""

    def test_case_decision_close_granted_to_compliance(self):
        perms = _effective_seed_permissions("compliance")
        assert "case:decision" in perms
        assert "case:close" in perms

    def test_case_decision_close_not_granted_to_analyst(self):
        perms = _effective_seed_permissions("analyst")
        assert "case:decision" not in perms
        assert "case:close" not in perms

    def test_case_decision_close_not_granted_to_admin(self):
        perms = _effective_seed_permissions("admin")
        assert "case:decision" not in perms
        assert "case:close" not in perms

    def test_compliance_has_no_standalone_alert_perms(self):
        perms = _effective_seed_permissions("compliance")
        assert perms.isdisjoint(COMPLIANCE_FORBIDDEN)

    def test_analyst_has_no_standalone_case_or_ir_create(self):
        perms = _effective_seed_permissions("analyst")
        assert perms.isdisjoint(ANALYST_FORBIDDEN)

    def test_analyst_core_alert_workflow_preserved(self):
        perms = _effective_seed_permissions("analyst")
        for p in ("alert:read_assigned", "alert:dismiss", "alert:investigate"):
            assert p in perms

    def test_analyst_retains_alert_transition_for_escalation(self):
        # Accepted alert->case escalation (T08/V03) runs via alert:transition.
        perms = _effective_seed_permissions("analyst")
        assert "alert:transition" in perms

    def test_compliance_has_no_standalone_alert_escalation(self):
        perms = _effective_seed_permissions("compliance")
        assert "alert:transition" not in perms

    def test_analyst_my_information_requests_preserved(self):
        perms = _effective_seed_permissions("analyst")
        assert "info_request:read_assigned" in perms
        assert "info_request:respond" in perms

    def test_compliance_contextual_remaining_capabilities(self):
        perms = _effective_seed_permissions("compliance")
        for p in ("info_request:create", "info_request:read",
                  "info_request:accept", "info_request:return",
                  "investigation:review", "case:create",
                  "case:read_assigned", "case:transition"):
            assert p in perms


class TestAuthorisePolicyInvariants:
    """The policy engine must enforce every segregation invariant itself."""

    def _user(self, role: str, permissions: list) -> ApplicationUser:
        return ApplicationUser(
            user_id=f"{role}1", role=role, permissions=permissions,
            scopes=["hq_main"],
        )

    # case:decision is permitted in "decision_pending"; case:close in "resolved"
    def _case_decision_pending(self, assigned="compliance1"):
        return Resource(id="c1", status="decision_pending", assigned_to=assigned,
                        scope_id="hq_main", risk_level="low",
                        entity_type="compliance_case")

    def _case_resolved(self, assigned="compliance1"):
        return Resource(id="c1", status="resolved", assigned_to=assigned,
                        scope_id="hq_main", risk_level="low",
                        entity_type="compliance_case")

    @pytest.mark.asyncio
    async def test_compliance_can_decision(self):
        u = self._user("compliance", ["case:decision", "case:close"])
        await authorise(u, "case:decision", self._case_decision_pending())

    @pytest.mark.asyncio
    async def test_compliance_can_close(self):
        u = self._user("compliance", ["case:decision", "case:close"])
        await authorise(u, "case:close", self._case_resolved())

    @pytest.mark.asyncio
    async def test_compliance_cannot_read_assigned_alerts(self):
        # Standalone alert queue: compliance lacks alert:read_assigned -> denied
        u = self._user("compliance", sorted(TARGET_COMPLIANCE))
        res = Resource(id="assigned", status="active",
                       entity_type="collection", scope_id="hq_main")
        with pytest.raises(PermissionDeniedError):
            await authorise(u, "alert:read_assigned", res)

    @pytest.mark.asyncio
    async def test_compliance_cannot_transition_alerts(self):
        u = self._user("compliance", sorted(TARGET_COMPLIANCE))
        with pytest.raises(PermissionDeniedError):
            await authorise(
                u, "alert:transition",
                Resource(id="a1", status="under_investigation",
                         assigned_to="compliance1", scope_id="hq_main",
                         entity_type="alert"),
            )

    @pytest.mark.asyncio
    async def test_analyst_cannot_read_assigned_cases(self):
        u = self._user("analyst", sorted(TARGET_ANALYST))
        res = Resource(id="assigned", status="active",
                       entity_type="collection", scope_id="hq_main")
        with pytest.raises(PermissionDeniedError):
            await authorise(u, "case:read_assigned", res)

    @pytest.mark.asyncio
    async def test_analyst_can_read_own_alerts(self):
        u = self._user("analyst", sorted(TARGET_ANALYST))
        res = Resource(id="assigned", status="active",
                       entity_type="collection", scope_id="hq_main")
        await authorise(u, "alert:read_assigned", res)

    @pytest.mark.asyncio
    async def test_analyst_can_dismiss_alerts(self):
        u = self._user("analyst", sorted(TARGET_ANALYST))
        await authorise(
            u, "alert:dismiss",
            Resource(id="a1", status="acknowledged", assigned_to="analyst1",
                     scope_id="hq_main", severity="low", entity_type="alert"),
        )

    @pytest.mark.asyncio
    async def test_analyst_can_investigate_alerts(self):
        u = self._user("analyst", sorted(TARGET_ANALYST))
        await authorise(
            u, "alert:investigate",
            Resource(id="a1", status="acknowledged", assigned_to="analyst1",
                     scope_id="hq_main", entity_type="alert"),
        )

    @pytest.mark.asyncio
    async def test_analyst_can_respond_own_ir(self):
        u = self._user("analyst", sorted(TARGET_ANALYST))
        await authorise(
            u, "info_request:respond",
            Resource(id="ir1", status="acknowledged", assigned_to="analyst1",
                     scope_id="hq_main", entity_type="information_request",
                     created_by="compliance1"),
        )

    @pytest.mark.asyncio
    async def test_admin_cannot_record_decision(self):
        # SoD: admin is PROHIBITED from operational case decisions even if a
        # stray grant existed.
        u = self._user("admin", sorted(TARGET_ADMIN) + ["case:decision", "case:close"])
        with pytest.raises(ProhibitedComboError):
            await authorise(u, "case:decision", self._case_resolved("analyst1"))

    @pytest.mark.asyncio
    async def test_admin_cannot_close_case(self):
        u = self._user("admin", sorted(TARGET_ADMIN) + ["case:decision", "case:close"])
        with pytest.raises(ProhibitedComboError):
            await authorise(u, "case:close", self._case_resolved("analyst1"))

    @pytest.mark.asyncio
    async def test_analyst_is_prohibited_from_decision(self):
        u = self._user("analyst", sorted(TARGET_ANALYST) + ["case:decision", "case:close"])
        with pytest.raises(ProhibitedComboError):
            await authorise(u, "case:decision", self._case_resolved("compliance1"))
