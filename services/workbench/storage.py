"""Private evidence storage subsystem for Phase 3A.9D.

Provides a clean storage abstraction (`EvidenceStorage`) for saving, retrieving,
and deleting evidence files on a persistent private volume without exposing
raw filesystem paths or static URL routes.
"""
from __future__ import annotations

import hashlib
import os
import re
from typing import BinaryIO, Optional, Tuple

from workbench.exceptions import FileTooLarge, WorkbenchError

# Default storage root (can be overridden via EVIDENCE_STORAGE_ROOT env var)
DEFAULT_STORAGE_ROOT = os.getenv("EVIDENCE_STORAGE_ROOT", "var/lib/banking/evidence")

# 10 MB default limit (10 * 1024 * 1024 bytes)
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

# Allowed mime types & extension mapping
ALLOWED_MIME_TYPES = {
    "application/pdf": {".pdf"},
    "image/png": {".png"},
    "image/jpeg": {".jpg", ".jpeg"},
    "text/csv": {".csv"},
    "text/plain": {".txt", ".csv"},
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {".xlsx"},
}

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".csv", ".xlsx", ".txt"}


def validate_file_type(original_filename: str, content_type: str) -> None:
    """Validate original filename extension and content type against strict allowlist."""
    ext = os.path.splitext(original_filename)[1].lower()
    if not ext or ext not in ALLOWED_EXTENSIONS:
        from workbench.exceptions import InvalidFileType
        raise InvalidFileType(content_type or "unknown", original_filename)

    # Sanitize content_type string (strip parameters like charset=utf-8)
    clean_mime = (content_type or "").split(";")[0].strip().lower()

    if clean_mime not in ALLOWED_MIME_TYPES:
        from workbench.exceptions import InvalidFileType
        raise InvalidFileType(clean_mime, original_filename)

    allowed_exts_for_mime = ALLOWED_MIME_TYPES[clean_mime]
    if ext not in allowed_exts_for_mime:
        from workbench.exceptions import InvalidFileType
        raise InvalidFileType(clean_mime, original_filename)


class EvidenceStorage:
    """Abstraction for private evidence storage operations."""

    def __init__(self, root_dir: Optional[str] = None) -> None:
        self.root_dir = os.path.abspath(root_dir or DEFAULT_STORAGE_ROOT)

    def _resolve_dir(self, scope_id: str, investigation_id: str) -> str:
        safe_scope = re.sub(r"[^a-zA-Z0-9_-]", "_", scope_id)
        safe_inv = re.sub(r"[^a-zA-Z0-9_-]", "_", investigation_id)
        target_dir = os.path.abspath(os.path.join(self.root_dir, safe_scope, safe_inv))

        # Path traversal guard
        if not target_dir.startswith(self.root_dir):
            raise WorkbenchError("INVALID_PATH", "Storage path traversal detected", 400)

        os.makedirs(target_dir, exist_ok=True)
        return target_dir

    def _resolve_file_path(self, scope_id: str, investigation_id: str, stored_filename: str) -> str:
        # stored_filename must strictly be alphanumeric/UUID + .bin
        if not re.match(r"^[a-zA-Z0-9_-]+\.bin$", stored_filename):
            raise WorkbenchError("INVALID_STORAGE_KEY", f"Invalid storage key: {stored_filename}", 400)

        dir_path = self._resolve_dir(scope_id, investigation_id)
        file_path = os.path.abspath(os.path.join(dir_path, stored_filename))

        if not file_path.startswith(dir_path):
            raise WorkbenchError("INVALID_PATH", "Storage path traversal detected", 400)

        return file_path

    def save(
        self, scope_id: str, investigation_id: str, attachment_id: str, file_obj: BinaryIO, max_bytes: int = MAX_FILE_SIZE_BYTES
    ) -> Tuple[str, str, int]:
        """Stream save file object to storage key {attachment_id}.bin.

        Calculates SHA-256 hash and byte size during streaming. Enforces max_bytes limit.
        Returns (stored_filename, sha256_hash, size_bytes).
        """
        stored_filename = f"{attachment_id}.bin"
        file_path = self._resolve_file_path(scope_id, investigation_id, stored_filename)

        hasher = hashlib.sha256()
        total_bytes = 0
        chunk_size = 64 * 1024  # 64 KB

        try:
            with open(file_path, "wb") as f:
                while True:
                    chunk = file_obj.read(chunk_size)
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > max_bytes:
                        raise FileTooLarge(total_bytes, max_bytes)
                    hasher.update(chunk)
                    f.write(chunk)
        except Exception:
            # Physical cleanup on failure
            if os.path.exists(file_path):
                try:
                    os.unlink(file_path)
                except OSError:
                    pass
            raise

        if total_bytes == 0:
            if os.path.exists(file_path):
                os.unlink(file_path)
            raise WorkbenchError("EMPTY_FILE", "Uploaded evidence file cannot be empty", 400)

        return stored_filename, hasher.hexdigest(), total_bytes

    def get_path(self, scope_id: str, investigation_id: str, stored_filename: str) -> str:
        """Get verified physical file path."""
        path = self._resolve_file_path(scope_id, investigation_id, stored_filename)
        if not os.path.exists(path):
            from workbench.exceptions import ResourceNotFound
            raise ResourceNotFound("Evidence file", stored_filename)
        return path

    def delete(self, scope_id: str, investigation_id: str, stored_filename: str) -> bool:
        """Physical deletion of file object. Returns True if deleted, False if not found."""
        try:
            path = self._resolve_file_path(scope_id, investigation_id, stored_filename)
            if os.path.exists(path):
                os.unlink(path)
                return True
            return False
        except Exception:
            return False

    def exists(self, scope_id: str, investigation_id: str, stored_filename: str) -> bool:
        """Check if storage key exists physically."""
        try:
            path = self._resolve_file_path(scope_id, investigation_id, stored_filename)
            return os.path.exists(path)
        except Exception:
            return False
