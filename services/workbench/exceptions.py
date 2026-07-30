"""Domain exceptions for workbench operations.

Each carries an error_code and http_status for centralised HTTP mapping.
"""
from __future__ import annotations


class WorkbenchError(Exception):
    def __init__(self, code: str, message: str, http_status: int = 400) -> None:
        self.code = code
        self.http_status = http_status
        super().__init__(message)

    def to_dict(self) -> dict:
        return {"error": self.code, "message": str(self)}


class ResourceNotFound(WorkbenchError):
    def __init__(self, entity: str, id: str) -> None:
        super().__init__("NOT_FOUND", f"{entity} not found: {id}", 404)


class PermissionDenied(WorkbenchError):
    def __init__(self, detail: str = "Permission denied") -> None:
        super().__init__("FORBIDDEN", detail, 403)


class InvalidTransition(WorkbenchError):
    def __init__(self, status: str, action: str) -> None:
        super().__init__("INVALID_TRANSITION",
                         f"Cannot {action} alert in status {status}", 409)


class VersionConflict(WorkbenchError):
    def __init__(self) -> None:
        super().__init__("VERSION_CONFLICT",
                         "Resource was modified by another user. Refresh and retry.", 409)


class ApprovalRequired(WorkbenchError):
    def __init__(self, action: str) -> None:
        super().__init__("APPROVAL_REQUIRED",
                         f"Approval required for action: {action}", 428)


class ApprovalConsumed(WorkbenchError):
    def __init__(self) -> None:
        super().__init__("APPROVAL_EXECUTED",
                         "Approval has already been consumed", 409)


class IdempotencyMismatch(WorkbenchError):
    def __init__(self) -> None:
        super().__init__("IDEMPOTENCY_MISMATCH",
                         "Idempotency key exists with different request parameters", 409)


class InvalidAssignee(WorkbenchError):
    def __init__(self, detail: str) -> None:
        super().__init__("INVALID_ASSIGNEE", detail, 400)
