from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from .db import execute, fetch_all, fetch_one
from .utils import login_required, roles_required

bp = Blueprint("main", __name__)


@bp.get("/healthz")
def healthz():
    """Comprobación pública y ligera para balanceadores/servicios cloud."""
    return {"status": "ok", "service": "jardines-de-la-costa-erp"}


@bp.route("/")
def index():
    from flask import g, redirect, url_for

    if g.get("user") is None:
        return redirect(url_for("auth.login"))
    return redirect(url_for("main.dashboard"))


@bp.route("/dashboard")
@login_required
def dashboard():
    roles = {row["name"] for row in g.get("user_roles", [])}
    if "admin" in roles and not roles.intersection({"gerencia", "coordinador_operativo", "supervisor_operaciones", "conductor", "jardinero"}):
        return redirect(url_for("admin.console"))
    if "conductor" in roles and not (roles & {"admin", "gerencia"}):
        return redirect(url_for("main.driver_home"))
    if roles and roles <= {"jardinero"}:
        return redirect(url_for("main.worker_dashboard"))
    supervisor_only = "supervisor_operaciones" in roles and not roles.intersection({"admin", "gerencia", "coordinador_operativo"})
    supervisor = fetch_one(
        "SELECT id FROM employees WHERE identification_number=? AND deleted_at IS NULL",
        (g.user["username"],),
    ) if supervisor_only else None
    supervisor_id = supervisor["id"] if supervisor else -1
    people_query = """
        SELECT COUNT(DISTINCT e.id) AS total
        FROM employees e
        JOIN crew_members cm ON cm.employee_id=e.id
        JOIN crews c ON c.id=cm.crew_id
        WHERE e.status='active' AND e.deleted_at IS NULL
          AND c.deleted_at IS NULL AND c.supervisor_employee_id=?
    """ if supervisor_only else "SELECT COUNT(*) AS total FROM employees WHERE status='active' AND deleted_at IS NULL"
    people_args = (supervisor_id,) if supervisor_only else ()
    project_filter = " AND EXISTS (SELECT 1 FROM crews c WHERE c.project_id=p.id AND c.supervisor_employee_id=? AND c.deleted_at IS NULL)" if supervisor_only else ""
    project_args = (supervisor_id,) if supervisor_only else ()
    incident_filter = " AND project_id IN (SELECT c.project_id FROM crews c WHERE c.supervisor_employee_id=? AND c.deleted_at IS NULL)" if supervisor_only else ""
    equipment_filter = " AND project_id IN (SELECT c.project_id FROM crews c WHERE c.supervisor_employee_id=? AND c.deleted_at IS NULL)" if supervisor_only else ""
    metrics = {
        "active_people": fetch_one(people_query, people_args)["total"] + (0 if supervisor_only else fetch_one("SELECT COUNT(*) AS total FROM contractors WHERE status='active' AND deleted_at IS NULL")["total"]),
        "active_projects": fetch_one("SELECT COUNT(*) AS total FROM projects p WHERE p.status='active' AND p.deleted_at IS NULL" + project_filter, project_args)["total"],
        "open_incidents": fetch_one("SELECT COUNT(*) AS total FROM sst_incidents WHERE status <> 'closed'" + incident_filter, (supervisor_id,) if supervisor_only else ())["total"],
        "equipment_due": fetch_one("SELECT COUNT(*) AS total FROM equipment WHERE deleted_at IS NULL AND next_service_date IS NOT NULL AND date(next_service_date) <= date('now', '+30 day')" + equipment_filter, (supervisor_id,) if supervisor_only else ())["total"],
        "employees_missing_arl": fetch_one(
            "SELECT COUNT(*) AS total FROM employees WHERE status='active' AND deleted_at IS NULL "
            "AND COALESCE(NULLIF(TRIM(arl), ''), '') = '' AND arl_reference_id IS NULL"
        )["total"],
        "projects_without_end_date": fetch_one(
            "SELECT COUNT(*) AS total FROM projects p WHERE p.deleted_at IS NULL "
            "AND (p.planned_end_date IS NULL OR TRIM(p.planned_end_date) = '')" + project_filter,
            project_args,
        )["total"],
    }
    user_roles = {row["name"] for row in g.get("user_roles", [])}
    can_people = bool(user_roles & {"admin", "gerencia", "rrhh", "asistente_administrativa", "supervisor_operaciones", "coordinador_operativo", "sst", "supervisor_sst"})
    can_operations = bool(user_roles & {"admin", "gerencia", "supervisor_operaciones", "coordinador_operativo", "conductor"})
    can_manage_operations = bool(user_roles & {"admin", "gerencia", "supervisor_operaciones", "coordinador_operativo"})
    can_sst = bool(user_roles & {"admin", "gerencia", "sst", "supervisor_sst", "supervisor_operaciones", "coordinador_operativo"})
    metric_links = {"active_people": "employees.employee_list" if can_people else "main.dashboard", "active_projects": "projects.project_list" if can_operations else "main.dashboard", "open_incidents": "sst.dashboard" if can_sst else "main.dashboard", "equipment_due": "resources.equipment_list" if can_operations else "main.dashboard"}
    recent_projects = fetch_all(
        """
        SELECT id, code, name, client_name, status, planned_end_date
        FROM projects p
        WHERE p.deleted_at IS NULL
        """ + project_filter + """
        ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END, planned_end_date IS NULL, planned_end_date
        LIMIT 8
        """, project_args
    )
    recent_telemetry = fetch_all(
        """
        SELECT event_type, severity, source_type, occurred_at
        FROM telemetry_events
        WHERE 1=1
        """ + (" AND project_id IN (SELECT c.project_id FROM crews c WHERE c.supervisor_employee_id=?)" if supervisor_only else "") + """
        ORDER BY received_at DESC
        LIMIT 6
        """, (supervisor_id,) if supervisor_only else ()
    )
    return render_template(
        "dashboard.html",
        metrics=metrics,
        recent_projects=recent_projects,
        recent_telemetry=recent_telemetry, metric_links=metric_links,
        can_create_project=can_manage_operations,
    )


@bp.get("/mi-operacion")
@login_required
def worker_dashboard():
    roles = {row["name"] for row in g.get("user_roles", [])}
    if not roles or not roles <= {"jardinero"}:
        return redirect(url_for("main.dashboard"))
    employee = fetch_one("SELECT * FROM employees WHERE identification_number=? AND deleted_at IS NULL", (g.user["username"],))
    if employee is None:
        return render_template("error.html", code=404, message="Tu usuario no está vinculado a un perfil de colaborador."), 404
    crews = fetch_all("""
        SELECT c.name, c.status, p.code AS project_code, p.name AS project_name,
               e.first_name || ' ' || e.last_name AS supervisor_name
        FROM crew_members cm JOIN crews c ON c.id=cm.crew_id
        LEFT JOIN projects p ON p.id=c.project_id LEFT JOIN employees e ON e.id=c.supervisor_employee_id
        WHERE cm.employee_id=? AND c.deleted_at IS NULL ORDER BY c.name
    """, (employee["id"],))
    return render_template("worker/dashboard.html", employee=employee, crews=crews)


@bp.get("/inicio-conductor")
@login_required
def driver_home():
    roles = {row["name"] for row in g.get("user_roles", [])}
    if "conductor" not in roles or roles.intersection({"admin", "gerencia"}):
        return redirect(url_for("main.dashboard"))
    employee = fetch_one("SELECT id, first_name, last_name, identification_number FROM employees WHERE identification_number=? AND deleted_at IS NULL", (g.user["username"],))
    if employee is None:
        return render_template("error.html", code=404, message="El conductor no está vinculado a un colaborador."), 404
    if "supervisor_operaciones" in roles and not roles.intersection({"admin", "gerencia", "coordinador_operativo"}):
        if current_employee is None:
            return render_template("error.html", code=403, message="Tu usuario no tiene un supervisor operativo vinculado."), 403
        supervised = fetch_one(
            """SELECT 1 FROM crew_members cm JOIN crews c ON c.id=cm.crew_id
               WHERE c.supervisor_employee_id=? AND cm.employee_id=? AND c.deleted_at IS NULL""",
            (current_employee["id"], employee["id"]),
        )
        if supervised is None:
            return render_template("error.html", code=403, message="Este conductor no pertenece a tus cuadrillas."), 403
    counts = {
        "projects": fetch_one("SELECT COUNT(*) AS total FROM project_assignments WHERE employee_id=?", (employee["id"],))["total"],
        "crews": fetch_one("SELECT COUNT(*) AS total FROM crew_members WHERE employee_id=?", (employee["id"],))["total"],
        "vehicles": fetch_one("SELECT COUNT(*) AS total FROM equipment WHERE assigned_driver_employee_id=? AND deleted_at IS NULL", (employee["id"],))["total"],
    }
    return render_template("driver/home.html", employee=employee, counts=counts)


@bp.get("/conductor")
@bp.get("/conductor/<int:driver_employee_id>")
@login_required
def driver_dashboard(driver_employee_id=None):
    from flask import g, render_template
    roles = {row["name"] for row in g.get("user_roles", [])}
    if not roles.intersection({"conductor", "admin", "gerencia", "coordinador_operativo", "supervisor_operaciones"}):
        return redirect(url_for("main.dashboard"))
    current_employee = fetch_one("SELECT * FROM employees WHERE identification_number=? AND deleted_at IS NULL", (g.user["username"],))
    if driver_employee_id is None:
        employee = current_employee
        if employee is None and roles.intersection({"admin", "gerencia", "coordinador_operativo", "supervisor_operaciones"}):
            drivers = fetch_all("SELECT id, first_name || ' ' || last_name AS name, identification_number, position FROM employees WHERE status='active' AND deleted_at IS NULL AND lower(position) LIKE '%conductor%' ORDER BY last_name, first_name")
            return render_template("driver/select.html", drivers=drivers)
    elif roles.intersection({"admin", "gerencia", "coordinador_operativo", "supervisor_operaciones"}):
        employee = fetch_one("SELECT * FROM employees WHERE id=? AND deleted_at IS NULL", (driver_employee_id,))
    else:
        employee = current_employee
    if driver_employee_id is not None and not roles.intersection({"admin", "gerencia", "coordinador_operativo", "supervisor_operaciones"}):
        return render_template("error.html", code=403, message="No puedes consultar el panel de otro conductor."), 403
    if employee is None:
        if driver_employee_id is None and roles.intersection({"admin", "gerencia", "coordinador_operativo", "supervisor_operaciones"}):
            drivers = fetch_all("SELECT id, first_name || ' ' || last_name AS name, identification_number, position FROM employees WHERE status='active' AND deleted_at IS NULL AND lower(position) LIKE '%conductor%' ORDER BY last_name, first_name")
            return render_template("driver/select.html", drivers=drivers)
        return render_template("error.html", code=404, message="El conductor no está vinculado a un colaborador."), 404
    projects = fetch_all("""
        SELECT p.code, p.name, p.location, p.status, 'Asignación directa' AS role
        FROM project_assignments pa JOIN projects p ON p.id=pa.project_id
        WHERE pa.employee_id=? AND p.deleted_at IS NULL
        UNION
        SELECT p.code, p.name, p.location, p.status, 'Por cuadrilla' AS role
        FROM crews c JOIN projects p ON p.id=c.project_id JOIN crew_members cm ON cm.crew_id=c.id
        WHERE cm.employee_id=? AND c.deleted_at IS NULL AND p.deleted_at IS NULL
        ORDER BY status, name
    """, (employee["id"], employee["id"]))
    crews = fetch_all("""
        SELECT c.name, c.status, c.notes, p.code AS project_code, e.first_name || ' ' || e.last_name AS supervisor_name
        FROM crew_members cm JOIN crews c ON c.id=cm.crew_id
        LEFT JOIN projects p ON p.id=c.project_id LEFT JOIN employees e ON e.id=c.supervisor_employee_id
        WHERE cm.employee_id=? AND c.deleted_at IS NULL ORDER BY c.name
    """, (employee["id"],))
    vehicles = fetch_all("""
        SELECT asset_code, name, equipment_type, brand, model, status, location,
               vehicle_restrictions, next_service_date
        FROM equipment WHERE assigned_driver_employee_id=? AND deleted_at IS NULL
        ORDER BY name
    """, (employee["id"],))
    collaborators = fetch_all("""
        SELECT dea.id, e.first_name || ' ' || e.last_name AS employee_name,
               e.identification_number, e.position, p.code AS project_code, dea.notes
        FROM driver_employee_assignments dea JOIN employees e ON e.id=dea.employee_id
        LEFT JOIN projects p ON p.id=dea.project_id
        WHERE dea.driver_employee_id=? AND dea.status='active' AND e.deleted_at IS NULL
        ORDER BY employee_name
    """, (employee["id"],))
    roles = {row["name"] for row in g.get("user_roles", [])}
    control_roles = {"admin", "gerencia", "coordinador_operativo"}
    if roles.intersection(control_roles):
        all_employees = fetch_all("SELECT id, first_name || ' ' || last_name AS name, identification_number FROM employees WHERE status='active' AND deleted_at IS NULL ORDER BY name")
        all_projects = fetch_all("SELECT id, code, name FROM projects WHERE deleted_at IS NULL ORDER BY code")
    elif "supervisor_operaciones" in roles and current_employee:
        all_employees = fetch_all(
            """SELECT DISTINCT e.id, e.first_name || ' ' || e.last_name AS name, e.identification_number
               FROM crew_members cm JOIN crews c ON c.id=cm.crew_id JOIN employees e ON e.id=cm.employee_id
               WHERE c.supervisor_employee_id=? AND c.deleted_at IS NULL AND e.status='active' AND e.deleted_at IS NULL
               ORDER BY name""",
            (current_employee["id"],),
        )
        all_projects = fetch_all(
            """SELECT DISTINCT p.id, p.code, p.name FROM crews c JOIN projects p ON p.id=c.project_id
               WHERE c.supervisor_employee_id=? AND c.deleted_at IS NULL AND p.deleted_at IS NULL ORDER BY p.code""",
            (current_employee["id"],),
        )
    else:
        all_employees, all_projects = [], []
    return render_template("driver/dashboard.html", employee=employee, projects=projects, crews=crews, vehicles=vehicles, collaborators=collaborators, all_employees=all_employees, all_projects=all_projects)


@bp.post("/conductor/<int:driver_employee_id>/colaboradores")
@login_required
@roles_required("admin", "gerencia", "coordinador_operativo", "supervisor_operaciones")
def driver_employee_assign(driver_employee_id):
    employee_id = request.form.get("employee_id")
    project_id = request.form.get("project_id") or None
    if not employee_id:
        flash("Selecciona un colaborador.", "danger")
        return redirect(url_for("main.driver_dashboard", driver_employee_id=driver_employee_id))
    execute("""INSERT OR REPLACE INTO driver_employee_assignments
        (driver_employee_id, employee_id, project_id, notes, status)
        VALUES (?, ?, ?, ?, 'active')""", (driver_employee_id, employee_id, project_id, request.form.get("notes", "").strip() or None))
    flash("Colaborador asignado directamente al conductor.", "success")
    return redirect(url_for("main.driver_dashboard", driver_employee_id=driver_employee_id))


@bp.post("/conductor/asignaciones/<int:assignment_id>/eliminar")
@login_required
@roles_required("admin", "gerencia", "coordinador_operativo", "supervisor_operaciones")
def driver_employee_unassign(assignment_id):
    assignment = fetch_one("SELECT driver_employee_id FROM driver_employee_assignments WHERE id=?", (assignment_id,))
    execute("UPDATE driver_employee_assignments SET status='inactive' WHERE id=?", (assignment_id,))
    flash("Asignación individual retirada.", "success")
    return redirect(url_for("main.driver_dashboard", driver_employee_id=assignment["driver_employee_id"] if assignment else None))
