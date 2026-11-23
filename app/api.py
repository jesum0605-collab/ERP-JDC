import json
from datetime import date
from io import BytesIO

from flask import Blueprint, current_app, jsonify, make_response, request, send_file

from .db import execute, fetch_all, fetch_one
from .utils import DELETE_TARGETS, delete_confirmation, login_required, roles_required, soft_delete_entity

bp = Blueprint("api", __name__)


LOOKUP_QUERIES = {
    "employees": """
        SELECT e.id, e.first_name || ' ' || e.last_name AS label,
               e.identification_number AS code, e.position, e.email, e.phone
        FROM employees e
        WHERE e.status='active' AND e.deleted_at IS NULL
          AND (e.first_name || ' ' || e.last_name LIKE ?
               OR e.identification_number LIKE ? OR COALESCE(e.position, '') LIKE ?)
        ORDER BY label LIMIT ?
    """,
    "contractors": """
        SELECT c.id, c.legal_name AS label, c.tax_id AS code,
               c.service_type, c.contact_name, c.email, c.phone
        FROM contractors c
        WHERE c.status='active' AND c.deleted_at IS NULL
          AND (c.legal_name LIKE ? OR c.tax_id LIKE ?
               OR COALESCE(c.service_type, '') LIKE ?)
        ORDER BY label LIMIT ?
    """,
    "crews": """
        SELECT c.id, c.name AS label, c.status,
               e.first_name || ' ' || e.last_name AS supervisor_name
        FROM crews c LEFT JOIN employees e ON e.id=c.supervisor_employee_id
        WHERE c.status='active' AND c.deleted_at IS NULL
          AND (c.name LIKE ? OR COALESCE(e.first_name || ' ' || e.last_name, '') LIKE ?)
        ORDER BY label LIMIT ?
    """,
    "projects": """
        SELECT p.id, p.code, p.name AS label, p.client_name, p.location, p.status,
               e.first_name || ' ' || e.last_name AS manager_name,
               (SELECT COUNT(*) FROM project_assignments pa WHERE pa.project_id=p.id) AS assignment_count,
               (SELECT COUNT(*) FROM project_phases ph WHERE ph.project_id=p.id) AS phase_count
        FROM projects p LEFT JOIN employees e ON e.id=p.project_manager_employee_id
        WHERE p.deleted_at IS NULL
          AND (p.code LIKE ? OR p.name LIKE ? OR COALESCE(p.client_name, '') LIKE ?
               OR COALESCE(p.location, '') LIKE ?)
        ORDER BY CASE p.status WHEN 'active' THEN 0 WHEN 'planning' THEN 1 ELSE 2 END, p.code
        LIMIT ?
    """,
    "materials": """
        SELECT m.id, m.sku AS code, m.name AS label, m.unit, m.current_stock,
               m.minimum_stock, m.unit_cost, m.supplier
        FROM materials m
        WHERE m.status='active' AND m.deleted_at IS NULL
          AND (m.sku LIKE ? OR m.name LIKE ? OR COALESCE(m.supplier, '') LIKE ?)
        ORDER BY label LIMIT ?
    """,
    "equipment": """
        SELECT e.id, e.asset_code AS code, e.name AS label, e.equipment_type,
               e.brand, e.model, e.status, e.location, p.code AS project_code
        FROM equipment e LEFT JOIN projects p ON p.id=e.project_id
        WHERE e.deleted_at IS NULL
          AND (e.asset_code LIKE ? OR e.name LIKE ? OR COALESCE(e.brand, '') LIKE ?
               OR COALESCE(e.location, '') LIKE ?)
        ORDER BY label LIMIT ?
    """,
}


@bp.get("/api/lookups/<resource>")
@login_required
@roles_required("admin", "gerencia", "rrhh", "asistente_administrativa", "coordinador_operativo", "supervisor_operaciones", "sst", "supervisor_sst", "conductor")
def lookup(resource):
    query = LOOKUP_QUERIES.get(resource)
    if query is None:
        return jsonify(error="Catálogo no disponible"), 404
    term = request.args.get("q", "").strip()
    pattern = f"%{term}%"
    try:
        limit = min(max(int(request.args.get("limit", 12)), 1), 30)
    except ValueError:
        limit = 12
    pattern_count = {"projects": 4, "equipment": 4, "crews": 2}.get(resource, 3)
    args = [pattern] * pattern_count
    args.append(limit)
    return jsonify(items=[dict(row) for row in fetch_all(query, args)])


@bp.get("/api/lookups/references/<catalog_code>")
@login_required
def reference_lookup(catalog_code):
    term = request.args.get("q", "").strip()
    try:
        limit = min(max(int(request.args.get("limit", 30)), 1), 60)
    except ValueError:
        limit = 30
    pattern = f"%{term}%"
    rows = fetch_all(
        """SELECT id, code, name, metadata_json
           FROM reference_items
           WHERE catalog_code=? AND is_active=1
             AND (?='' OR code LIKE ? OR name LIKE ?)
           ORDER BY sort_order, name LIMIT ?""",
        (catalog_code, term, pattern, pattern, limit),
    )
    return jsonify(items=[dict(row) for row in rows])


@bp.get("/api/records/<resource>/<int:record_id>/context")
@login_required
@roles_required("admin", "gerencia", "rrhh", "asistente_administrativa", "coordinador_operativo", "supervisor_operaciones", "sst", "supervisor_sst", "conductor")
def record_context(resource, record_id):
    if resource == "project":
        project = fetch_one(
            """
            SELECT p.*, e.first_name || ' ' || e.last_name AS manager_name
            FROM projects p LEFT JOIN employees e ON e.id=p.project_manager_employee_id
            WHERE p.id=? AND p.deleted_at IS NULL
            """, (record_id,)
        )
        if project is None:
            return jsonify(error="Registro no encontrado"), 404
        return jsonify(
            record=dict(project),
            phases=[dict(row) for row in fetch_all(
                "SELECT name, planned_start, planned_end, progress_percent, status FROM project_phases WHERE project_id=? ORDER BY sequence LIMIT 8",
                (record_id,),
            )],
            resources=[dict(row) for row in fetch_all(
                """
                SELECT COALESCE(e.first_name || ' ' || e.last_name, c.legal_name, cr.name) AS name,
                       pa.role, pa.assigned_from, pa.assigned_to
                FROM project_assignments pa
                LEFT JOIN employees e ON e.id=pa.employee_id
                LEFT JOIN contractors c ON c.id=pa.contractor_id
                LEFT JOIN crews cr ON cr.id=pa.crew_id
                WHERE pa.project_id=? ORDER BY pa.id DESC LIMIT 12
                """, (record_id,),
            )],
            equipment=[dict(row) for row in fetch_all(
                "SELECT asset_code, name, status, location FROM equipment WHERE project_id=? AND deleted_at IS NULL ORDER BY name",
                (record_id,),
            )],
            materials=[dict(row) for row in fetch_all(
                """
                SELECT m.sku, m.name, m.unit,
                       SUM(CASE WHEN im.movement_type IN ('in','return') THEN im.quantity ELSE -im.quantity END) AS quantity
                FROM inventory_movements im JOIN materials m ON m.id=im.material_id
                WHERE im.project_id=? GROUP BY m.id ORDER BY m.name
                """, (record_id,),
            )],
            sst=[dict(row) for row in fetch_all(
                """
                SELECT 'incident' AS record_type, incident_type AS type, severity, occurred_at AS record_date, status
                FROM sst_incidents WHERE project_id=?
                UNION ALL
                SELECT 'inspection', 'inspection', CAST(compliance_percent AS TEXT), inspection_date, status
                FROM sst_inspections WHERE project_id=?
                ORDER BY record_date DESC LIMIT 12
                """, (record_id, record_id),
            )],
        )
    if resource == "employee":
        employee = fetch_one(
            """
            SELECT id, identification_number, first_name || ' ' || last_name AS name,
                   email, phone, position, hire_date, status, arl, eps, pension_fund
            FROM employees WHERE id=? AND deleted_at IS NULL
            """, (record_id,)
        )
        if employee is None:
            return jsonify(error="Registro no encontrado"), 404
        evaluation = fetch_one(
            """
            SELECT evaluation_date, performance_score, potential_score, nine_box_cell,
                   strengths, development_plan
            FROM performance_evaluations WHERE employee_id=?
            ORDER BY evaluation_date DESC, id DESC LIMIT 1
            """, (record_id,)
        )
        return jsonify(
            record=dict(employee),
            projects=[dict(row) for row in fetch_all(
                """
                SELECT p.id, p.code, p.name, pa.role, pa.assigned_from, pa.assigned_to
                FROM project_assignments pa JOIN projects p ON p.id=pa.project_id
                WHERE pa.employee_id=? AND p.deleted_at IS NULL ORDER BY p.status, p.name
                """, (record_id,),
            )],
            latest_evaluation=dict(evaluation) if evaluation else None,
            incidents=[dict(row) for row in fetch_all(
                "SELECT incident_type, severity, occurred_at, status FROM sst_incidents WHERE employee_id=? ORDER BY occurred_at DESC LIMIT 8",
                (record_id,),
            )],
        )
    return jsonify(error="Contexto no disponible"), 404


def kpi_values():
    compliance = fetch_one(
        "SELECT ROUND(COALESCE(AVG(compliance_percent), 0), 1) AS value FROM sst_inspections"
    )["value"]
    return {
        "generated_at": date.today().isoformat(),
        "active_people": fetch_one(
            """
            SELECT
              (SELECT COUNT(*) FROM employees WHERE status='active' AND deleted_at IS NULL) +
              (SELECT COUNT(*) FROM contractors WHERE status='active' AND deleted_at IS NULL) AS value
            """
        )["value"],
        "active_projects": fetch_one(
            "SELECT COUNT(*) AS value FROM projects WHERE status='active' AND deleted_at IS NULL"
        )["value"],
        "sst_compliance_percent": compliance,
        "open_incidents": fetch_one(
            "SELECT COUNT(*) AS value FROM sst_incidents WHERE status <> 'closed'"
        )["value"],
        "equipment_available": fetch_one(
            "SELECT COUNT(*) AS value FROM equipment WHERE status='available' AND deleted_at IS NULL"
        )["value"],
    }


@bp.get("/api/kpis")
@login_required
@roles_required("admin", "gerencia", "rrhh", "asistente_administrativa", "coordinador_operativo", "supervisor_operaciones", "sst", "supervisor_sst")
def kpis():
    return jsonify(kpi_values())


@bp.post("/api/<resource>/<int:record_id>/delete")
@login_required
@roles_required("admin", "gerencia")
def universal_delete(resource, record_id):
    """Eliminación lógica única para entidades principales.

    Requiere confirm=1 y solo permite recursos incluidos en DELETE_TARGETS.
    """
    if resource not in DELETE_TARGETS:
        return jsonify(error="Recurso no permitido"), 404
    if not delete_confirmation(request):
        return jsonify(error="La confirmación es obligatoria"), 400
    if not soft_delete_entity(resource, record_id):
        return jsonify(error="Registro inexistente o ya eliminado"), 404
    return jsonify(status="deleted", resource=resource, id=record_id)


@bp.get("/reportes/kpis.pdf")
@login_required
@roles_required("admin", "gerencia", "rrhh", "asistente_administrativa", "coordinador_operativo", "supervisor_operaciones", "sst", "supervisor_sst")
def kpi_pdf():
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        from reportlab.lib import colors
    except ImportError:
        return jsonify(error="Instala la dependencia reportlab para generar PDF"), 503

    values = kpi_values()
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Jardines de la Costa S.A.S.", styles["Title"]),
        Paragraph("Reporte consolidado de indicadores clave", styles["Heading2"]),
        Spacer(1, 14),
    ]
    rows = [["Indicador", "Valor"], ["Generado", values["generated_at"]], ["Personal activo", str(values["active_people"])], ["Proyectos activos", str(values["active_projects"])], ["Cumplimiento SST", f'{values["sst_compliance_percent"]}%'], ["Incidentes abiertos", str(values["open_incidents"])], ["Equipos disponibles", str(values["equipment_available"])]]
    table = Table(rows, colWidths=[300, 160])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0fdfa")]),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(table)
    document.build(story)
    buffer.seek(0)
    return send_file(buffer, mimetype="application/pdf", as_attachment=True, download_name="reporte-kpis.pdf")
