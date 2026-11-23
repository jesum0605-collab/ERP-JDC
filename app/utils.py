import hmac
import json
import secrets
import uuid
from datetime import datetime, timezone
from functools import wraps

from flask import abort, g, redirect, request, session, url_for

from .db import get_db


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def validate_csrf():
    expected = session.get("csrf_token")
    supplied = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
    return bool(expected and supplied and hmac.compare_digest(expected, supplied))


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.get("user") is None:
            if request.is_json or request.path.startswith("/api/"):
                abort(401)
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped_view


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            current_roles = {row["name"] for row in g.get("user_roles", [])}
            if "operaciones" in roles:
                if current_roles.intersection({"supervisor_operaciones", "coordinador_operativo"}):
                    current_roles.add("operaciones")
            if "sst" in roles:
                if current_roles.intersection({"supervisor_sst"}):
                    current_roles.add("sst")
            if not current_roles.intersection(roles):
                abort(403)
            return view(*args, **kwargs)

        return wrapped_view

    return decorator


DELETE_TARGETS = {
    "employees": ("employees", "id"),
    "contractors": ("contractors", "id"),
    "crews": ("crews", "id"),
    "projects": ("projects", "id"),
    "materials": ("materials", "id"),
    "equipment": ("equipment", "id"),
}


def delete_confirmation(request_data):
    if hasattr(request_data, "get_json"):
        if request_data.is_json:
            payload = request_data.get_json(silent=True) or {}
            return str(payload.get("confirm", "")) == "1"
        return str(request_data.form.get("confirm", "")) == "1"
    return str(request_data.get("confirm", "")) == "1"


def soft_delete_entity(resource, record_id):
    from flask import g

    from .db import execute

    target = DELETE_TARGETS.get(resource)
    if not target:
        return False
    table, key = target
    cursor = execute(
        f"UPDATE {table} SET deleted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE {key} = ? AND deleted_at IS NULL",
        (record_id,),
    )
    if cursor.rowcount == 1:
        current_user = g.get("user")
        audit_event("soft_delete", "system", resource, record_id)
        return True
    return False


SENSITIVE_AUDIT_KEYS = {"password", "password_hash", "token", "secret", "api_key", "bank_account", "account_number"}


def _audit_safe(value):
    if isinstance(value, dict):
        return {str(k): ("[REDACTED]" if str(k).lower() in SENSITIVE_AUDIT_KEYS else _audit_safe(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_audit_safe(item) for item in value]
    if isinstance(value, bytes):
        return "[BINARY]"
    return value


def audit_event(action, module, entity_type, entity_id=None, *, result="success", reason=None, before=None, after=None, correlation_id=None, metadata=None):
    """Write one sanitized audit event using the caller's current transaction."""
    current_user = g.get("user")
    correlation_id = correlation_id or g.get("audit_correlation_id") or str(uuid.uuid4())
    db = get_db()
    db.execute(
        """INSERT INTO audit_log
        (user_id, action, module, entity_type, entity_id, result, reason,
         before_json, after_json, correlation_id, metadata_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            current_user["id"] if current_user else None,
            action, module, entity_type, entity_id, result, reason,
            json.dumps(_audit_safe(before), ensure_ascii=False, default=str) if before is not None else None,
            json.dumps(_audit_safe(after), ensure_ascii=False, default=str) if after is not None else None,
            correlation_id,
            json.dumps(_audit_safe(metadata), ensure_ascii=False, default=str) if metadata is not None else None,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    # Fuera de una transacción explícita, el evento debe persistir junto con
    # la operación individual que acaba de ejecutarse. Dentro de transaction()
    # queda pendiente del mismo COMMIT/ROLLBACK empresarial.
    if not g.get("transaction_depth"):
        db.commit()
    return correlation_id
