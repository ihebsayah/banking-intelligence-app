"""Domain service for Phase 3A.9D Evidence Attachments.

Handles file validation, physical storage streaming, metadata persistence,
parent-investigation authorization, audit logging, and UoW compensation.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, BinaryIO, Dict, List, Optional, Tuple

from shared.authorise import ApplicationUser, RequestContext, Resource, authorise
from shared.database import DatabaseConnector
from workbench.exceptions import (
    InvalidTransition, ResourceNotFound, VersionConflict, WorkbenchError,
)
from workbench.models import (
    ActivityTimelineEntry, AuditOutboxEvent, Investigation, InvestigationAttachment,
)
from workbench.repos import (
    AttachmentRepo, InvestigationRepo, OutboxRepo, TimelineRepo,
)
from workbench.schemas.attachments import AttachmentListResponse, AttachmentResponse
from workbench.storage import EvidenceStorage, validate_file_type
from workbench.uow import UnitOfWork


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _resource_from_inv(inv: Investigation) -> Resource:
    return Resource(
        id=inv.investigation_id, status=inv.status,
        assigned_to=inv.assigned_to, scope_id=inv.scope_id,
        version=inv.version, entity_type="investigation",
    )


def _make_timeline(entity_type: str, entity_id: str, event_type: str, actor_id: str,
                   old_value: Optional[Dict[str, Any]], new_value: Optional[Dict[str, Any]]) -> ActivityTimelineEntry:
    return ActivityTimelineEntry(
        timeline_id=_uuid(), entity_type=entity_type, entity_id=entity_id,
        event_type=event_type, actor_id=actor_id,
        old_value=old_value, new_value=new_value, occurred_at=_now(),
    )


def _make_outbox(event_type: str, entity_type: str, entity_id: str,
                 actor_id: str, actor_role: str, payload: Dict[str, Any]) -> AuditOutboxEvent:
    return AuditOutboxEvent(
        outbox_id=_uuid(),
        idempotency_key=f"{entity_type}.{entity_id}.{event_type}.{_uuid()}",
        event_type=event_type, entity_type=entity_type, entity_id=entity_id,
        actor_id=actor_id, actor_role=actor_role,
        occurred_at=_now(), payload=payload,
    )


class AttachmentService:
    def __init__(self, db: DatabaseConnector, storage: Optional[EvidenceStorage] = None) -> None:
        self._db = db
        self._storage = storage or EvidenceStorage()

    async def upload_attachment(
        self,
        user: ApplicationUser,
        investigation_id: str,
        original_filename: str,
        content_type: str,
        file_obj: BinaryIO,
        description: Optional[str] = None,
        request_id: str = "",
    ) -> AttachmentResponse:
        # Step 1: Validate file type & extension allowlist
        validate_file_type(original_filename, content_type)

        attachment_id = _uuid()
        stored_filename = None
        scope_id = "hq_main"

        async with UnitOfWork(self._db) as uow:
            inv = await InvestigationRepo(self._db).fetch_by_id(investigation_id, uow.conn)
            if inv is None:
                raise ResourceNotFound("Investigation", investigation_id)

            scope_id = inv.scope_id

            # Authorize via parent investigation
            await authorise(user, "investigation:modify_findings",
                            _resource_from_inv(inv), self._db,
                            RequestContext(request_id=request_id))

            # Editable state check
            if inv.status not in ("open", "active", "returned"):
                raise InvalidTransition(inv.status, "upload_attachment")

            # Stream save file to physical private storage
            stored_filename, sha256_hash, size_bytes = self._storage.save(
                scope_id=inv.scope_id,
                investigation_id=investigation_id,
                attachment_id=attachment_id,
                file_obj=file_obj,
            )

            att = InvestigationAttachment(
                attachment_id=attachment_id,
                investigation_id=investigation_id,
                original_filename=original_filename,
                stored_filename=stored_filename,
                content_type=content_type,
                size_bytes=size_bytes,
                sha256_hash=sha256_hash,
                description=description,
                uploaded_by=user.user_id,
                uploaded_at=_now(),
            )

            try:
                await AttachmentRepo(self._db).create(att, uow.conn)
            except Exception:
                # Compensation: delete physical storage object if DB record write fails
                if stored_filename:
                    self._storage.delete(scope_id, investigation_id, stored_filename)
                raise

            # Timeline event on investigation
            await TimelineRepo(self._db).insert(
                _make_timeline("investigation", investigation_id,
                              "investigation.attachment_uploaded", user.user_id,
                              None,
                              {"attachment_id": attachment_id,
                               "content_type": content_type,
                               "size_bytes": size_bytes,
                               "sha256_hash": sha256_hash}),
                uow.conn)

            # Audit outbox event
            await OutboxRepo(self._db).insert(
                _make_outbox("investigation.attachment_uploaded", "investigation",
                            investigation_id, user.user_id, user.role,
                            {"investigation_id": investigation_id,
                             "attachment_id": attachment_id,
                             "content_type": content_type,
                             "size_bytes": size_bytes,
                             "sha256_hash": sha256_hash}),
                uow.conn)

            return AttachmentResponse(**att.model_dump())

    async def list_attachments(
        self,
        user: ApplicationUser,
        investigation_id: str,
        request_id: str = "",
    ) -> AttachmentListResponse:
        async with UnitOfWork(self._db) as uow:
            inv = await InvestigationRepo(self._db).fetch_by_id(investigation_id, uow.conn)
            if inv is None:
                raise ResourceNotFound("Investigation", investigation_id)

            try:
                perm = "investigation:review" if user.role == "compliance" else "investigation:read"
                await authorise(user, perm, _resource_from_inv(inv), self._db, RequestContext(request_id=request_id))
            except WorkflowStateError:
                await authorise(user, "investigation:read", _resource_from_inv(inv), self._db, RequestContext(request_id=request_id))

            items = await AttachmentRepo(self._db).list_by_investigation(investigation_id, uow.conn)
            responses = [AttachmentResponse(**a.model_dump()) for a in items]
            return AttachmentListResponse(total=len(responses), items=responses)

    async def get_attachment_for_download(
        self,
        user: ApplicationUser,
        investigation_id: str,
        attachment_id: str,
        request_id: str = "",
    ) -> Tuple[AttachmentResponse, str]:
        async with UnitOfWork(self._db) as uow:
            inv = await InvestigationRepo(self._db).fetch_by_id(investigation_id, uow.conn)
            if inv is None:
                raise ResourceNotFound("Investigation", investigation_id)

            try:
                perm = "investigation:review" if user.role == "compliance" else "investigation:read"
                await authorise(user, perm, _resource_from_inv(inv), self._db, RequestContext(request_id=request_id))
            except WorkflowStateError:
                await authorise(user, "investigation:read", _resource_from_inv(inv), self._db, RequestContext(request_id=request_id))

            att = await AttachmentRepo(self._db).fetch_by_id_and_investigation(
                attachment_id, investigation_id, uow.conn)
            if att is None:
                raise ResourceNotFound("Attachment", attachment_id)

            file_path = self._storage.get_path(inv.scope_id, investigation_id, att.stored_filename)

            # Audit download event
            await OutboxRepo(self._db).insert(
                _make_outbox("investigation.attachment_downloaded", "investigation",
                            investigation_id, user.user_id, user.role,
                            {"investigation_id": investigation_id,
                             "attachment_id": attachment_id,
                             "downloaded_by": user.user_id}),
                uow.conn)

            return AttachmentResponse(**att.model_dump()), file_path

    async def delete_attachment(
        self,
        user: ApplicationUser,
        investigation_id: str,
        attachment_id: str,
        request_id: str = "",
    ) -> bool:
        async with UnitOfWork(self._db) as uow:
            inv = await InvestigationRepo(self._db).fetch_by_id(investigation_id, uow.conn)
            if inv is None:
                raise ResourceNotFound("Investigation", investigation_id)

            await authorise(user, "investigation:modify_findings",
                            _resource_from_inv(inv), self._db,
                            RequestContext(request_id=request_id))

            if inv.status not in ("open", "active", "returned"):
                raise InvalidTransition(inv.status, "delete_attachment")

            att = await AttachmentRepo(self._db).fetch_by_id_and_investigation(
                attachment_id, investigation_id, uow.conn)
            if att is None:
                raise ResourceNotFound("Attachment", attachment_id)

            deleted = await AttachmentRepo(self._db).delete(attachment_id, uow.conn)
            if deleted:
                self._storage.delete(inv.scope_id, investigation_id, att.stored_filename)

                await TimelineRepo(self._db).insert(
                    _make_timeline("investigation", investigation_id,
                                  "investigation.attachment_deleted", user.user_id,
                                  {"attachment_id": attachment_id}, None),
                    uow.conn)

                await OutboxRepo(self._db).insert(
                    _make_outbox("investigation.attachment_deleted", "investigation",
                                investigation_id, user.user_id, user.role,
                                {"investigation_id": investigation_id,
                                 "attachment_id": attachment_id}),
                    uow.conn)

            return deleted
