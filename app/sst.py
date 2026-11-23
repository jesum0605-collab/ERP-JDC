import hmac
import json
import sqlite3
from datetime import datetime, timezone

from flask import Blueprint, current_app, flash, g, jsonify, redirect, render_template, request, url_for

from .db import execute, fetch_all, fetch_one
from .utils import audit_event, login_required, roles_required

bp = Blueprint("sst", __name__)

REPORT_TYPES = {
    "sst_incident": "Incidente SST",
    "near_miss": "Casi accidente",
    "vehicle": "Novedad del vehículo",
    "maintenance": "Mantenimiento o falla mecánica",
    "traffic": "Novedad vial o de tránsito",
    "documentation": "Documentación o vencimiento",
    "operational": "Novedad operativa",
    "personnel": "Novedad con personal",
    "other": "Otra novedad",
}


def dashboard_data():
    compliance = fetch_one(
        "SELECT ROUND(COALESCE(AVG(compliance_percent), 0), 1) AS value FROM sst_inspections"
    )["value"]
    return {
        "compliance_percent": compliance,
        "open_incidents": fetch_one("SELECT COUNT(*) AS value FROM sst_incidents WHERE status <> 'closed'")["value"],
        "critical_events_30d": fetch_one(
            """
            SELECT COUNT(*) AS value FROM telemetry_events
            WHERE severity IN ('high', 'critical') AND datetime(occurred_at) >= datetime('now', '-30 day')
            """
        )["value"],
        "inspections_30d": fetch_one(
            "SELECT COUNT(*) AS value FROM sst_inspections WHERE date(inspection_date) >= date('now', '-30 day')"
        )["value"],
        "recent_events": [dict(row) for row in fetch_all(
            """
            SELECT id, source_type, device_id, event_type, severity, occurred_at, received_at
            FROM telemetry_events ORDER BY received_at DESC LIMIT 12
            """
        )],
        "recent_inspections": [dict(row) for row in fetch_all(
            """
            SELECT si.id, si.inspection_date, si.compliance_percent, si.status,
                   p.code AS project_code, u.full_name AS inspector_name
            FROM sst_inspections si
            LEFT JOIN projects p ON p.id = si.project_id
            LEFT JOIN users u ON u.id = si.inspector_user_id
            ORDER BY si.inspection_date DESC, si.id DESC LIMIT 6
            """
        )],
        "recent_incidents": [dict(row) for row in fetch_all(
            """
            SELECT si.id, si.report_type, si.incident_type, si.severity, si.occurred_at, si.status,
                   p.code AS project_code
            FROM sst_incidents si LEFT JOIN projects p ON p.id = si.project_id
            ORDER BY si.occurred_at DESC, si.id DESC LIMIT 6
            """
        )],
    }


@bp.get("/sst")
@login_required
@roles_required("admin", "gerencia", "sst", "supervisor_sst", "operaciones", "coordinador_operativo")
def dashboard():
    return render_template("sst/dashboard.html", data=dashboard_data(), report_types=REPORT_TYPES)


@bp.get("/api/sst/dashboard")
@login_required
@roles_required("admin", "gerencia", "sst", "supervisor_sst", "operaciones", "coordinador_operativo")
def dashboard_api():
    return jsonify(dashboard_data())


@bp.route("/sst/inspecciones/nueva", methods=("GET", "POST"))
@login_required
@roles_required("admin", "gerencia", "sst", "supervisor_sst", "operaciones", "coordinador_operativo")
def inspection_create():
    projects = fetch_all("SELECT id, code, name FROM projects WHERE deleted_at IS NULL ORDER BY code")
    if request.method == "POST":
        try:
            compliance = float(request.form.get("compliance_percent") or 0)
            if not 0 <= compliance <= 100:
                raise ValueError
            created = execute(
                """
                INSERT INTO sst_inspections
                (project_id, inspection_date, inspector_user_id, compliance_percent, findings, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    request.form.get("project_id") or None, request.form.get("inspection_date"),
                    g.user["id"], compliance, request.form.get("findings", "").strip() or None,
                    request.form.get("status", "open"),
                ),
            )
            audit_event("create", "sst", "sst_inspections", created.lastrowid, after={"project_id": request.form.get("project_id"), "compliance_percent": compliance})
            flash("Inspección SST registrada.", "success")
            return redirect(url_for("sst.dashboard"))
        except (TypeError, ValueError, sqlite3.IntegrityError):
            flash("Verifica la fecha, el porcentaje y los datos de la inspección.", "danger")
    return render_template("sst/inspection_form.html", projects=projects)


@bp.route("/sst/incidentes/nuevo", methods=("GET", "POST"))
@login_required
@roles_required("admin", "gerencia", "sst", "supervisor_sst", "operaciones", "coordinador_operativo", "conductor")
def incident_create():
    roles = {row["name"] for row in g.get("user_roles", [])}
    conductor_employee = fetch_one("SELECT id FROM employees WHERE identification_number=? AND deleted_at IS NULL", (g.user["username"],)) if "conductor" in roles else None
    projects = fetch_all("SELECT id, code, name FROM projects WHERE deleted_at IS NULL ORDER BY code")
    if conductor_employee:
        projects = fetch_all("""
            SELECT DISTINCT p.id, p.code, p.name FROM projects p
            LEFT JOIN project_assignments pa ON pa.project_id=p.id AND pa.employee_id=?
            LEFT JOIN crews c ON c.project_id=p.id AND c.deleted_at IS NULL
            LEFT JOIN crew_members cm ON cm.crew_id=c.id AND cm.employee_id=?
            WHERE p.deleted_at IS NULL AND (pa.id IS NOT NULL OR cm.id IS NOT NULL) ORDER BY p.code
        """, (conductor_employee["id"], conductor_employee["id"]))
    employees = fetch_all(
        "SELECT id, first_name || ' ' || last_name AS name FROM employees WHERE status='active' AND deleted_at IS NULL ORDER BY name"
    )
    if request.method == "POST":
        try:
            project_id = request.form.get("project_id") or None
            report_type = request.form.get("report_type", "sst_incident")
            if report_type not in REPORT_TYPES:
                raise ValueError("Tipo de reporte no válido.")
            if conductor_employee and project_id:
                allowed_project = fetch_one("""
                    SELECT 1 WHERE EXISTS (SELECT 1 FROM project_assignments WHERE project_id=? AND employee_id=?)
                    OR EXISTS (SELECT 1 FROM crews c JOIN crew_members cm ON cm.crew_id=c.id WHERE c.project_id=? AND cm.employee_id=? AND c.deleted_at IS NULL)
                """, (project_id, conductor_employee["id"], project_id, conductor_employee["id"]))
                if allowed_project is None:
                    raise ValueError("El proyecto no está asignado al conductor.")
            occurred_at = request.form.get("occurred_at") or datetime.now(timezone.utc).isoformat(timespec="minutes")
            created = execute(
                """
                INSERT INTO sst_incidents
                (project_id, employee_id, report_type, incident_type, severity, occurred_at, description, reported_by_user_id, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open')
                """,
                (
                    project_id,
                    conductor_employee["id"] if conductor_employee else request.form.get("employee_id") or None,
                    report_type,
                    request.form.get("incident_type", "unsafe_condition"), request.form.get("severity", "medium"),
                    occurred_at, request.form.get("description", "").strip(), g.user["id"],
                ),
            )
            audit_event("create", "sst", "sst_incidents", created.lastrowid, after={"report_type": report_type, "incident_type": request.form.get("incident_type"), "severity": request.form.get("severity")})
            flash("Novedad registrada correctamente.", "success")
            if conductor_employee:
                return redirect(url_for("main.driver_home"))
            return redirect(url_for("sst.dashboard"))
        except (ValueError, sqlite3.IntegrityError):
            flash("Verifica el tipo, severidad y los datos del incidente.", "danger")
    return render_template("sst/incident_form.html", projects=projects, employees=employees, report_types=REPORT_TYPES)


@bp.post("/sst/incidentes/<int:incident_id>/estado")
@login_required
@roles_required("admin", "gerencia", "sst", "supervisor_sst", "operaciones", "coordinador_operativo")
def incident_status(incident_id):
    status = request.form.get("status", "investigating")
    if status not in {"open", "investigating", "closed"}:
        flash("Estado de incidente no válido.", "danger")
    else:
        before = fetch_one("SELECT status FROM sst_incidents WHERE id=?", (incident_id,))
        execute("UPDATE sst_incidents SET status=? WHERE id=?", (status, incident_id))
        audit_event("change_status", "sst", "sst_incidents", incident_id, before=dict(before) if before else None, after={"status": status})
        flash("Estado del incidente actualizado.", "success")
    return redirect(url_for("sst.dashboard"))


def _valid_api_key_or_session():
    configured_key = current_app.config.get("TELEMETRY_API_KEY", "")
    provided_key = request.headers.get("X-API-Key", "")
    if configured_key:
        return bool(provided_key and hmac.compare_digest(configured_key, provided_key))
    return g.get("user") is not None


@bp.post("/api/sst/incidents")
def receive_incident():
    if not _valid_api_key_or_session():
        return jsonify(error="API key inválida"), 401
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="El cuerpo debe ser un objeto JSON"), 400
    required = ("severity", "occurred_at", "description")
    missing = [field for field in required if not payload.get(field)]
    if missing:
        return jsonify(error="Faltan campos obligatorios", fields=missing), 422
    report_type = payload.get("report_type", "sst_incident")
    if report_type not in REPORT_TYPES:
        return jsonify(error="report_type no válido"), 422
    incident_type = payload.get("incident_type", "unsafe_condition")
    if incident_type not in {"near_miss", "accident", "illness", "unsafe_condition"}:
        return jsonify(error="incident_type no válido"), 422
    if payload["severity"] not in {"low", "medium", "high", "critical"}:
        return jsonify(error="severity no válido"), 422
    try:
        incident_id = execute(
            """
            INSERT INTO sst_incidents
            (project_id, employee_id, report_type, incident_type, severity, occurred_at, description, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'open')
            """,
            (
                payload.get("project_id"), payload.get("employee_id"), payload["report_type"], incident_type,
                payload["severity"], payload["occurred_at"], payload["description"],
            ),
        ).lastrowid
        audit_event("create", "sst", "sst_incidents", incident_id, metadata={"source": "api"})
    except sqlite3.IntegrityError:
        return jsonify(error="project_id o employee_id no válidos"), 422
    return jsonify(id=incident_id, status="accepted"), 201


@bp.post("/api/telemetry")
def receive_telemetry():
    configured_key = current_app.config.get("TELEMETRY_API_KEY", "")
    provided_key = request.headers.get("X-API-Key", "")
    if configured_key:
        if not provided_key or not hmac.compare_digest(configured_key, provided_key):
            return jsonify(error="API key inválida"), 401
    elif g.get("user") is None:
        return jsonify(error="Configura TELEMETRY_API_KEY o autentica la solicitud"), 401

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="El cuerpo debe ser un objeto JSON"), 400
    required = ("source_type", "event_type", "occurred_at")
    missing = [field for field in required if not payload.get(field)]
    if missing:
        return jsonify(error="Faltan campos obligatorios", fields=missing), 422
    if payload.get("severity", "info") not in {"info", "low", "medium", "high", "critical"}:
        return jsonify(error="severity no válido"), 422
    try:
        payload_json = json.dumps(payload.get("payload", payload), ensure_ascii=False)
        event_id = execute(
            """
            INSERT INTO telemetry_events
            (source_type, device_id, project_id, employee_id, event_type, severity,
             latitude, longitude, payload_json, occurred_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["source_type"], payload.get("device_id"), payload.get("project_id"),
                payload.get("employee_id"), payload["event_type"], payload.get("severity", "info"),
                payload.get("latitude"), payload.get("longitude"), payload_json, payload["occurred_at"],
            ),
        ).lastrowid
        audit_event("receive", "sst", "telemetry_events", event_id, metadata={"source": "api", "event_type": payload.get("event_type")})
    except (TypeError, ValueError):
        return jsonify(error="El cuerpo JSON no es válido"), 400
    except sqlite3.IntegrityError:
        return jsonify(error="project_id o employee_id no válidos"), 422
    return jsonify(id=event_id, status="accepted"), 201
