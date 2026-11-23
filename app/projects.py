import sqlite3

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from .db import execute, fetch_all, fetch_one
from .utils import audit_event, delete_confirmation, login_required, roles_required, soft_delete_entity

bp = Blueprint("projects", __name__, url_prefix="/proyectos")


@bp.get("")
@login_required
@roles_required("admin", "gerencia", "coordinador_operativo", "supervisor_operaciones", "conductor")
def project_list():
    roles = {row["name"] for row in g.get("user_roles", [])}
    scope = ""
    args = []
    if "supervisor_operaciones" in roles and not roles.intersection({"admin", "gerencia", "coordinador_operativo"}):
        employee = fetch_one("SELECT id FROM employees WHERE identification_number=? AND deleted_at IS NULL", (g.user["username"],))
        scope = """ AND EXISTS (SELECT 1 FROM crews c
                         WHERE c.project_id=p.id AND c.supervisor_employee_id=? AND c.deleted_at IS NULL)"""
        args = [employee["id"] if employee else -1]
    elif roles.intersection({"conductor", "jardinero"}):
        scope = """ AND (EXISTS (SELECT 1 FROM project_assignments pa WHERE pa.project_id=p.id AND pa.employee_id=?)
                         OR EXISTS (SELECT 1 FROM crews c JOIN crew_members cm ON cm.crew_id=c.id
                                    WHERE c.project_id=p.id AND cm.employee_id=? AND c.deleted_at IS NULL))"""
        employee = fetch_one("SELECT id FROM employees WHERE identification_number=? AND deleted_at IS NULL", (g.user["username"],))
        employee_id = employee["id"] if employee else -1
        args = [employee_id, employee_id]
    projects = fetch_all(
        """
        SELECT p.*, e.first_name || ' ' || e.last_name AS manager_name,
               (SELECT COUNT(*) FROM project_phases ph WHERE ph.project_id = p.id) AS phase_count,
               COALESCE((SELECT AVG(ph.progress_percent) FROM project_phases ph WHERE ph.project_id = p.id), 0) AS progress
        FROM projects p
        LEFT JOIN employees e ON e.id = p.project_manager_employee_id
        WHERE p.deleted_at IS NULL
        """ + scope + """
        ORDER BY CASE p.status WHEN 'active' THEN 0 WHEN 'planning' THEN 1 ELSE 2 END, p.planned_end_date
        """ , args
    )
    return render_template("projects/list.html", projects=projects)


@bp.route("/nuevo", methods=("GET", "POST"))
@login_required
@roles_required("admin", "gerencia", "coordinador_operativo")
def project_create():
    if request.method == "POST":
        data = request.form
        if not data.get("code", "").strip() or not data.get("name", "").strip():
            flash("Código y nombre del proyecto son obligatorios.", "danger")
        else:
            try:
                project_id = execute(
                    """
                    INSERT INTO projects
                    (code, name, client_name, client_contact, description, location, start_date,
                     planned_end_date, budget, status, project_manager_employee_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        data["code"].strip(), data["name"].strip(), data.get("client_name", "").strip() or None,
                        data.get("client_contact", "").strip() or None, data.get("description", "").strip() or None,
                        data.get("location", "").strip() or None, data.get("start_date") or None,
                        data.get("planned_end_date") or None, data.get("budget") or 0,
                        data.get("status", "planning"), data.get("project_manager_employee_id") or None,
                    ),
                ).lastrowid
                audit_event("create", "projects", "projects", project_id, after={"code": data.get("code"), "name": data.get("name"), "status": data.get("status", "planning")})
                flash("Proyecto creado correctamente.", "success")
                return redirect(url_for("projects.project_detail", project_id=project_id))
            except sqlite3.IntegrityError:
                flash("El código ya existe o los datos no son válidos.", "danger")
    managers = fetch_all(
        "SELECT id, first_name || ' ' || last_name AS name FROM employees WHERE status='active' AND deleted_at IS NULL ORDER BY name"
    )
    return render_template("projects/form.html", project=None, managers=managers)


@bp.route("/<int:project_id>/editar", methods=("GET", "POST"))
@login_required
@roles_required("admin", "gerencia", "coordinador_operativo")
def project_edit(project_id):
    project = fetch_one("SELECT * FROM projects WHERE id = ? AND deleted_at IS NULL", (project_id,))
    if project is None:
        return render_template("error.html", code=404, message="Proyecto no encontrado."), 404
    if request.method == "POST":
        data = request.form
        try:
            execute(
                """
                UPDATE projects SET code=?, name=?, client_name=?, client_contact=?, description=?, location=?,
                    start_date=?, planned_end_date=?, actual_end_date=?, budget=?, status=?,
                    project_manager_employee_id=?, updated_at=CURRENT_TIMESTAMP
                WHERE id = ? AND deleted_at IS NULL
                """,
                (
                    data["code"].strip(), data["name"].strip(), data.get("client_name", "").strip() or None,
                    data.get("client_contact", "").strip() or None, data.get("description", "").strip() or None,
                    data.get("location", "").strip() or None, data.get("start_date") or None,
                    data.get("planned_end_date") or None, data.get("actual_end_date") or None,
                    data.get("budget") or 0, data.get("status", "planning"),
                    data.get("project_manager_employee_id") or None, project_id,
                ),
            )
            audit_event("update", "projects", "projects", project_id, after={"name": data.get("name"), "status": data.get("status"), "budget": data.get("budget"), "manager": data.get("project_manager_employee_id")})
            flash("Proyecto actualizado.", "success")
            return redirect(url_for("projects.project_detail", project_id=project_id))
        except sqlite3.IntegrityError:
            flash("El código ya existe o los datos no son válidos.", "danger")
    managers = fetch_all(
        "SELECT id, first_name || ' ' || last_name AS name FROM employees WHERE status='active' AND deleted_at IS NULL ORDER BY name"
    )
    return render_template("projects/form.html", project=project, managers=managers)


@bp.get("/<int:project_id>")
@login_required
@roles_required("admin", "gerencia", "coordinador_operativo", "supervisor_operaciones", "conductor")
def project_detail(project_id):
    project = fetch_one(
        """
        SELECT p.*, e.first_name || ' ' || e.last_name AS manager_name
        FROM projects p LEFT JOIN employees e ON e.id = p.project_manager_employee_id
        WHERE p.id = ? AND p.deleted_at IS NULL
        """,
        (project_id,),
    )
    if project is None:
        return render_template("error.html", code=404, message="Proyecto no encontrado."), 404
    roles = {row["name"] for row in g.get("user_roles", [])}
    if "supervisor_operaciones" in roles and not roles.intersection({"admin", "gerencia", "coordinador_operativo"}):
        employee = fetch_one("SELECT id FROM employees WHERE identification_number=? AND deleted_at IS NULL", (g.user["username"],))
        allowed = fetch_one("SELECT 1 FROM crews WHERE project_id=? AND supervisor_employee_id=? AND deleted_at IS NULL", (project_id, employee["id"] if employee else -1))
        if allowed is None:
            return render_template("error.html", code=403, message="Este proyecto no está asignado a tus cuadrillas."), 403
    elif roles.intersection({"conductor", "jardinero"}):
        employee = fetch_one("SELECT id FROM employees WHERE identification_number=? AND deleted_at IS NULL", (g.user["username"],))
        employee_id = employee["id"] if employee else -1
        allowed = fetch_one("""
            SELECT 1 WHERE EXISTS (SELECT 1 FROM project_assignments WHERE project_id=? AND employee_id=?)
            OR EXISTS (SELECT 1 FROM crews c JOIN crew_members cm ON cm.crew_id=c.id WHERE c.project_id=? AND cm.employee_id=? AND c.deleted_at IS NULL)
        """, (project_id, employee_id, project_id, employee_id))
        if allowed is None:
            return render_template("error.html", code=403, message="Este proyecto no está asignado a tu operación."), 403
    phases = fetch_all(
        "SELECT * FROM project_phases WHERE project_id = ? ORDER BY sequence", (project_id,)
    )
    assignments = fetch_all(
        """
        SELECT pa.role, pa.assigned_from, pa.assigned_to,
               CASE WHEN pa.employee_id IS NOT NULL THEN e.first_name || ' ' || e.last_name
                    WHEN pa.contractor_id IS NOT NULL THEN c.legal_name
                    WHEN pa.crew_id IS NOT NULL THEN cr.name END AS resource_name
        FROM project_assignments pa
        LEFT JOIN employees e ON e.id = pa.employee_id
        LEFT JOIN contractors c ON c.id = pa.contractor_id
        LEFT JOIN crews cr ON cr.id = pa.crew_id
        WHERE pa.project_id = ?
        ORDER BY pa.id DESC
        """,
        (project_id,),
    )
    employees = fetch_all(
        "SELECT id, first_name || ' ' || last_name AS name FROM employees WHERE status='active' AND deleted_at IS NULL ORDER BY name"
    )
    contractors = fetch_all("SELECT id, legal_name AS name FROM contractors WHERE status='active' AND deleted_at IS NULL ORDER BY name")
    crews = fetch_all("SELECT id, name FROM crews WHERE status='active' AND deleted_at IS NULL ORDER BY name")
    return render_template(
        "projects/detail.html", project=project, phases=phases, assignments=assignments,
        employees=employees, contractors=contractors, crews=crews,
    )


@bp.post("/<int:project_id>/eliminar")
@login_required
@roles_required("admin", "gerencia", "coordinador_operativo")
def project_delete(project_id):
    if not delete_confirmation(request):
        flash("Debes confirmar la eliminación.", "warning")
    elif soft_delete_entity("projects", project_id):
        flash("Proyecto eliminado de forma lógica.", "success")
    else:
        flash("El proyecto no existe o ya fue eliminado.", "warning")
    return redirect(url_for("projects.project_list"))


@bp.post("/<int:project_id>/fases")
@login_required
@roles_required("admin", "gerencia", "coordinador_operativo")
def phase_create(project_id):
    project = fetch_one("SELECT id FROM projects WHERE id = ? AND deleted_at IS NULL", (project_id,))
    if project is None:
        return render_template("error.html", code=404, message="Proyecto no encontrado."), 404
    data = request.form
    try:
        phase_id = execute(
            """
            INSERT INTO project_phases (project_id, name, sequence, planned_start, planned_end, progress_percent, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id, data.get("name", "").strip(), data.get("sequence") or 1,
                data.get("planned_start") or None, data.get("planned_end") or None,
                data.get("progress_percent") or 0, data.get("status", "pending"),
            ),
        ).lastrowid
        audit_event("create", "projects", "project_phases", phase_id, metadata={"project_id": project_id})
        flash("Fase agregada al cronograma.", "success")
    except sqlite3.IntegrityError:
        flash("No se pudo agregar la fase. Verifica nombre, secuencia y progreso.", "danger")
    return redirect(url_for("projects.project_detail", project_id=project_id))


@bp.post("/<int:project_id>/asignaciones")
@login_required
@roles_required("admin", "gerencia", "coordinador_operativo")
def assignment_create(project_id):
    project = fetch_one("SELECT id FROM projects WHERE id=? AND deleted_at IS NULL", (project_id,))
    if project is None:
        return render_template("error.html", code=404, message="Proyecto no encontrado."), 404
    resource_type = request.form.get("resource_type")
    resource_id = request.form.get("resource_id")
    if resource_type not in {"employee", "contractor", "crew"} or not resource_id:
        flash("Selecciona un recurso válido.", "danger")
        return redirect(url_for("projects.project_detail", project_id=project_id))
    column = {"employee": "employee_id", "contractor": "contractor_id", "crew": "crew_id"}[resource_type]
    source_table = {"employee": "employees", "contractor": "contractors", "crew": "crews"}[resource_type]
    resource = fetch_one(
        f"SELECT id FROM {source_table} WHERE id=? AND status='active' AND deleted_at IS NULL",
        (resource_id,),
    )
    if resource is None:
        flash("El recurso seleccionado no está activo o no corresponde al tipo indicado.", "danger")
        return redirect(url_for("projects.project_detail", project_id=project_id))
    try:
        assignment_id = execute(
            f"INSERT INTO project_assignments (project_id, {column}, role, assigned_from, assigned_to) VALUES (?, ?, ?, ?, ?)",
            (
                project_id, resource_id, request.form.get("role", "").strip() or None,
                request.form.get("assigned_from") or None, request.form.get("assigned_to") or None,
            ),
        ).lastrowid
        audit_event("create", "projects", "project_assignments", assignment_id, metadata={"project_id": project_id, "resource_type": resource_type})
        flash("Recurso asignado al proyecto.", "success")
    except sqlite3.IntegrityError:
        flash("No se pudo asignar el recurso. Verifica los datos.", "danger")
    return redirect(url_for("projects.project_detail", project_id=project_id))
