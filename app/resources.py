import sqlite3

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from .db import execute, fetch_all, fetch_one, transaction
from .utils import audit_event, login_required, roles_required

bp = Blueprint("resources", __name__, url_prefix="/recursos")


@bp.get("/materiales")
@login_required
@roles_required("admin", "gerencia", "coordinador_operativo", "supervisor_operaciones", "conductor")
def materials_list():
    materials = fetch_all(
        "SELECT * FROM materials WHERE deleted_at IS NULL ORDER BY name"
    )
    return render_template("resources/materials.html", materials=materials)


@bp.route("/materiales/nuevo", methods=("GET", "POST"))
@login_required
@roles_required("admin", "gerencia", "coordinador_operativo", "supervisor_operaciones")
def material_create():
    if request.method == "POST":
        data = request.form
        try:
            material_id = execute(
                """
                INSERT INTO materials (sku, name, unit, minimum_stock, current_stock, unit_cost, supplier)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data.get("sku", "").strip(), data.get("name", "").strip(), data.get("unit", "").strip(),
                    data.get("minimum_stock") or 0, data.get("current_stock") or 0,
                    data.get("unit_cost") or 0, data.get("supplier", "").strip() or None,
                ),
            ).lastrowid
            audit_event("create", "inventory", "materials", material_id, after={"sku": data.get("sku"), "name": data.get("name"), "status": data.get("status", "active")})
            flash("Material registrado.", "success")
            return redirect(url_for("resources.materials_list"))
        except sqlite3.IntegrityError:
            flash("El SKU ya existe o faltan datos obligatorios.", "danger")
    return render_template("resources/material_form.html")


@bp.post("/materiales/<int:material_id>/movimiento")
@login_required
@roles_required("admin", "gerencia", "coordinador_operativo", "supervisor_operaciones")
def material_movement(material_id):
    material = fetch_one("SELECT * FROM materials WHERE id = ? AND deleted_at IS NULL", (material_id,))
    if material is None:
        return render_template("error.html", code=404, message="Material no encontrado."), 404
    movement_type = request.form.get("movement_type", "in")
    try:
        quantity = float(request.form.get("quantity") or 0)
    except (TypeError, ValueError):
        quantity = 0
    if movement_type not in {"in", "out", "return", "adjustment"} or quantity <= 0:
        flash("Tipo o cantidad de movimiento no válidos.", "danger")
        return redirect(url_for("resources.materials_list"))
    delta = -quantity if movement_type == "out" else quantity
    new_stock = float(material["current_stock"] or 0) + delta
    if new_stock < 0:
        flash("El movimiento dejaría el inventario en negativo.", "danger")
        return redirect(url_for("resources.materials_list"))
    with transaction():
        movement_id = execute(
            "INSERT INTO inventory_movements (material_id, project_id, movement_type, quantity, unit_cost, reference, created_by_user_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                material_id, request.form.get("project_id") or None, movement_type, quantity,
                request.form.get("unit_cost") or material["unit_cost"] or 0,
                request.form.get("reference", "").strip() or None, g.user["id"],
            ),
        ).lastrowid
        execute("UPDATE materials SET current_stock=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (new_stock, material_id))
        audit_event("inventory_movement", "inventory", "inventory_movements", movement_id, after={"material_id": material_id, "movement_type": movement_type, "quantity": quantity, "stock_after": new_stock})
    flash("Movimiento de inventario registrado.", "success")
    return redirect(url_for("resources.materials_list"))


@bp.get("/maquinaria")
@login_required
@roles_required("admin", "gerencia", "coordinador_operativo", "supervisor_operaciones", "conductor")
def equipment_list():
    roles = {row["name"] for row in g.get("user_roles", [])}
    scope = ""
    args = []
    if "conductor" in roles and not roles.intersection({"admin", "gerencia", "coordinador_operativo", "supervisor_operaciones"}):
        employee = fetch_one("SELECT id FROM employees WHERE identification_number=? AND deleted_at IS NULL", (g.user["username"],))
        scope = " AND eq.assigned_driver_employee_id=?"
        args = [employee["id"] if employee else -1]
    equipment = fetch_all(
        """
        SELECT eq.*, p.code AS project_code,
               (SELECT COUNT(*) FROM equipment_maintenance em WHERE em.equipment_id = eq.id AND em.status='scheduled') AS pending_maintenance
        FROM equipment eq LEFT JOIN projects p ON p.id = eq.project_id
        WHERE eq.deleted_at IS NULL""" + scope + " ORDER BY eq.name", args
    )
    return render_template("resources/equipment.html", equipment=equipment)


@bp.route("/maquinaria/nueva", methods=("GET", "POST"))
@login_required
@roles_required("admin", "gerencia", "coordinador_operativo", "supervisor_operaciones")
def equipment_create():
    projects = fetch_all("SELECT id, code, name FROM projects WHERE status IN ('planning','active') AND deleted_at IS NULL ORDER BY code")
    if request.method == "POST":
        data = request.form
        try:
            equipment_id = execute(
                """
                INSERT INTO equipment (asset_code, name, equipment_type, brand, model, serial_number, status, location, project_id, assigned_driver_employee_id, vehicle_restrictions, next_service_date, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data.get("asset_code", "").strip(), data.get("name", "").strip(), data.get("equipment_type", "").strip() or None,
                    data.get("brand", "").strip() or None, data.get("model", "").strip() or None,
                    data.get("serial_number", "").strip() or None, data.get("status", "available"),
                    data.get("location", "").strip() or None, data.get("project_id") or None,
                    data.get("assigned_driver_employee_id") or None, data.get("vehicle_restrictions", "").strip() or None,
                    data.get("next_service_date") or None, data.get("notes", "").strip() or None,
                ),
            ).lastrowid
            audit_event("create", "equipment", "equipment", equipment_id, after={"asset_code": data.get("asset_code"), "name": data.get("name"), "status": data.get("status", "available")})
            flash("Maquinaria registrada.", "success")
            return redirect(url_for("resources.equipment_list"))
        except sqlite3.IntegrityError:
            flash("El código de activo ya existe o los datos no son válidos.", "danger")
    drivers = fetch_all("SELECT id, first_name || ' ' || last_name AS name, identification_number FROM employees WHERE status='active' AND deleted_at IS NULL AND position LIKE '%Conductor%' ORDER BY name")
    return render_template("resources/equipment_form.html", projects=projects, drivers=drivers)


@bp.post("/maquinaria/<int:equipment_id>/mantenimiento")
@login_required
@roles_required("admin", "gerencia", "coordinador_operativo", "supervisor_operaciones")
def maintenance_create(equipment_id):
    equipment = fetch_one("SELECT id FROM equipment WHERE id=? AND deleted_at IS NULL", (equipment_id,))
    if equipment is None:
        return render_template("error.html", code=404, message="Equipo no encontrado."), 404
    with transaction():
        maintenance_id = execute(
            """
            INSERT INTO equipment_maintenance
            (equipment_id, maintenance_type, scheduled_date, provider, cost, description, status)
            VALUES (?, ?, ?, ?, ?, ?, 'scheduled')
            """,
            (
                equipment_id, request.form.get("maintenance_type", "preventive"), request.form.get("scheduled_date"),
                request.form.get("provider", "").strip() or None, request.form.get("cost") or 0,
                request.form.get("description", "").strip() or None,
            ),
        ).lastrowid
        execute("UPDATE equipment SET next_service_date=?, status='maintenance', updated_at=CURRENT_TIMESTAMP WHERE id=?", (request.form.get("scheduled_date"), equipment_id))
        audit_event("schedule_maintenance", "equipment", "equipment_maintenance", maintenance_id, metadata={"equipment_id": equipment_id})
    flash("Mantenimiento programado.", "success")
    return redirect(url_for("resources.equipment_list"))


@bp.get("/auditorias")
@login_required
@roles_required("admin", "gerencia", "coordinador_operativo", "supervisor_operaciones", "sst")
def audits_list():
    audits = fetch_all(
        """
        SELECT a.*, p.code AS project_code, u.full_name AS auditor_name,
               (SELECT COUNT(*) FROM action_plans ap WHERE ap.audit_id=a.id AND ap.status <> 'completed') AS open_actions
        FROM audits a LEFT JOIN projects p ON p.id=a.project_id LEFT JOIN users u ON u.id=a.auditor_user_id
        ORDER BY a.audit_date DESC, a.id DESC
        """
    )
    plans = fetch_all(
        """
        SELECT ap.*, e.first_name || ' ' || e.last_name AS responsible_name
        FROM action_plans ap LEFT JOIN employees e ON e.id = ap.responsible_employee_id
        ORDER BY ap.due_date IS NULL, ap.due_date
        """
    )
    plans_by_audit = {}
    for plan in plans:
        plans_by_audit.setdefault(plan["audit_id"], []).append(plan)
    employees = fetch_all(
        "SELECT id, first_name || ' ' || last_name AS name FROM employees WHERE status='active' AND deleted_at IS NULL ORDER BY name"
    )
    return render_template("resources/audits.html", audits=audits, plans_by_audit=plans_by_audit, employees=employees)


@bp.route("/auditorias/nueva", methods=("GET", "POST"))
@login_required
@roles_required("admin", "gerencia", "coordinador_operativo", "supervisor_operaciones", "sst")
def audit_create():
    projects = fetch_all("SELECT id, code, name FROM projects WHERE deleted_at IS NULL ORDER BY code")
    if request.method == "POST":
        audit_id = execute(
            "INSERT INTO audits (project_id, audit_type, audit_date, auditor_user_id, score, findings) VALUES (?, ?, ?, ?, ?, ?)",
            (
                request.form.get("project_id") or None, request.form.get("audit_type", "operational"),
                request.form.get("audit_date"), g.user["id"],
                request.form.get("score") or None, request.form.get("findings", "").strip() or None,
            ),
        ).lastrowid
        audit_event("create", "sst", "audits", audit_id, after={"audit_type": request.form.get("audit_type"), "project_id": request.form.get("project_id")})
        flash("Auditoría registrada.", "success")
        return redirect(url_for("resources.audits_list"))
    return render_template("resources/audit_form.html", projects=projects)


@bp.post("/auditorias/<int:audit_id>/planes")
@login_required
@roles_required("admin", "gerencia", "coordinador_operativo", "supervisor_operaciones", "sst")
def action_plan_create(audit_id):
    audit = fetch_one("SELECT id FROM audits WHERE id=?", (audit_id,))
    if audit is None:
        return render_template("error.html", code=404, message="Auditoría no encontrada."), 404
    plan_id = execute(
        "INSERT INTO action_plans (audit_id, description, responsible_employee_id, due_date, evidence_url) VALUES (?, ?, ?, ?, ?)",
        (
            audit_id, request.form.get("description", "").strip(), request.form.get("responsible_employee_id") or None,
            request.form.get("due_date") or None, request.form.get("evidence_url", "").strip() or None,
        ),
    ).lastrowid
    flash("Plan de acción creado.", "success")
    audit_event("create", "sst", "action_plans", plan_id, after={"audit_id": audit_id, "responsible_employee_id": request.form.get("responsible_employee_id"), "due_date": request.form.get("due_date")})
    return redirect(url_for("resources.audits_list"))


@bp.post("/planes/<int:plan_id>/estado")
@login_required
@roles_required("admin", "gerencia", "coordinador_operativo", "supervisor_operaciones", "sst")
def action_plan_status(plan_id):
    status = request.form.get("status", "in_progress")
    if status not in {"open", "in_progress", "completed", "overdue"}:
        flash("Estado no válido.", "danger")
    else:
        execute(
            "UPDATE action_plans SET status=?, completed_at=CASE WHEN ?='completed' THEN CURRENT_TIMESTAMP ELSE NULL END WHERE id=?",
            (status, status, plan_id),
        )
        audit_event("change_status", "sst", "action_plans", plan_id, after={"status": status})
        flash("Estado del plan de acción actualizado.", "success")
    return redirect(url_for("resources.audits_list"))
