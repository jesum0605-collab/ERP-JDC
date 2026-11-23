import sqlite3
from pathlib import Path

from flask import Blueprint, current_app, flash, g, jsonify, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from .db import execute, fetch_all, fetch_one, transaction
from .utils import audit_event, delete_confirmation, login_required, roles_required, soft_delete_entity

bp = Blueprint("employees", __name__, url_prefix="/rrhh")


MANAGER_ROLES = {"admin", "gerencia", "rrhh", "coordinador_operativo"}
VIEW_ALL_ROLES = MANAGER_ROLES | {"sst", "supervisor_sst"}


def can_manage_people():
    return bool({row["name"] for row in g.get("user_roles", [])} & MANAGER_ROLES)


def can_view_all_people():
    return bool({row["name"] for row in g.get("user_roles", [])} & VIEW_ALL_ROLES)


def current_employee():
    username = (g.user["username"] or "").strip() if g.get("user") else ""
    return fetch_one("SELECT * FROM employees WHERE identification_number=? AND deleted_at IS NULL", (username,)) if username else None


def reference_id(catalog, value):
    if not value:
        return None
    row = fetch_one("SELECT id FROM reference_items WHERE catalog_code=? AND (code=? OR name=?) AND is_active=1", (catalog, value.strip(), value.strip()))
    return row["id"] if row else None


@bp.get("/empleados")
@login_required
def employee_list():
    if not can_view_all_people():
        return redirect(url_for("employees.my_profile"))
    search = request.args.get("q", "").strip()
    like = f"%{search}%"
    query = """
        SELECT e.*, COALESCE(eps_ref.name, e.eps) AS eps_display,
               COALESCE(arl_ref.name, e.arl) AS arl_display,
               COALESCE(pension_ref.name, e.pension_fund) AS pension_display
        FROM employees e
        LEFT JOIN reference_items eps_ref ON eps_ref.id=e.eps_reference_id
        LEFT JOIN reference_items arl_ref ON arl_ref.id=e.arl_reference_id
        LEFT JOIN reference_items pension_ref ON pension_ref.id=e.pension_fund_reference_id
        WHERE e.deleted_at IS NULL
          AND (? = '' OR e.identification_number LIKE ? OR e.first_name LIKE ? OR e.last_name LIKE ?)
    """
    args = [search, like, like, like]
    query += " ORDER BY e.first_name, e.last_name"
    employees = fetch_all(
        query, args,
    )
    return render_template("employees/list.html", employees=employees, search=search, mode="employees", can_manage=can_manage_people())


@bp.route("/empleados/nuevo", methods=("GET", "POST"))
@login_required
@roles_required("admin", "gerencia", "rrhh", "coordinador_operativo")
def employee_create():
    if request.method == "POST":
        data = request.form
        required = [data.get("identification_number", "").strip(), data.get("first_name", "").strip(), data.get("last_name", "").strip()]
        if not all(required):
            flash("Identificación, nombres y apellidos son obligatorios.", "danger")
        else:
            try:
                created_employee_id = execute(
                    """
                    INSERT INTO employees
                    (identification_number, first_name, last_name, email, phone, position,
                     hire_date, salary_type, pay_frequency, base_salary, eps, pension_fund, arl, document_type, blood_type,
                     eps_reference_id, pension_fund_reference_id, arl_reference_id, bank_name, bank_account,
                     bank_reference_id, emergency_contact_name, emergency_contact_phone, emergency_contact_relationship,
                     education_level, marital_status, status, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        data["identification_number"].strip(), data["first_name"].strip(), data["last_name"].strip(),
                        data.get("email", "").strip() or None, data.get("phone", "").strip() or None,
                        data.get("position", "").strip() or None, data.get("hire_date") or None,
                        data.get("salary_type") or None, data.get("pay_frequency") or "biweekly", data.get("base_salary") or 0,
                        data.get("eps", "").strip() or None, data.get("pension_fund", "").strip() or None,
                        data.get("arl", "").strip() or None, data.get("document_type", "").strip() or None,
                        data.get("blood_type", "").strip() or None, reference_id("eps", data.get("eps", "")),
                        reference_id("pension_fund", data.get("pension_fund", "")), reference_id("arl", data.get("arl", "")),
                        data.get("bank_name", "").strip() or None, data.get("bank_account", "").strip() or None,
                        reference_id("bank", data.get("bank_name", "")), data.get("emergency_contact_name", "").strip() or None,
                        data.get("emergency_contact_phone", "").strip() or None, data.get("emergency_contact_relationship", "").strip() or None,
                        data.get("education_level", "").strip() or None, data.get("marital_status", "").strip() or None,
                        data.get("status", "active"),
                        data.get("notes", "").strip() or None,
                    ),
                ).lastrowid
                # Vincula automáticamente una cuenta existente cuyo usuario sea
                # el documento del nuevo colaborador.
                execute("UPDATE users SET employee_id=? WHERE username=? AND employee_id IS NULL", (created_employee_id, data["identification_number"].strip()))
                audit_event("create", "rrhh", "employees", created_employee_id, after={"identification_number": data.get("identification_number"), "position": data.get("position"), "status": data.get("status", "active")})
                flash("Empleado creado correctamente.", "success")
                return redirect(url_for("employees.employee_list"))
            except sqlite3.IntegrityError:
                flash("La identificación ya existe o los datos no son válidos.", "danger")
    return render_template("employees/form.html", employee=None, mode="employee")


@bp.route("/empleados/<int:employee_id>/editar", methods=("GET", "POST"))
@login_required
@roles_required("admin", "gerencia", "rrhh", "coordinador_operativo")
def employee_edit(employee_id):
    employee = fetch_one("SELECT * FROM employees WHERE id = ? AND deleted_at IS NULL", (employee_id,))
    if employee is None:
        return render_template("error.html", code=404, message="Empleado no encontrado."), 404
    if request.method == "POST":
        data = request.form
        try:
            execute(
                """
                UPDATE employees SET identification_number=?, first_name=?, last_name=?, email=?, phone=?,
                    position=?, hire_date=?, contract_end_date=?, salary_type=?, pay_frequency=?, base_salary=?, eps=?, pension_fund=?, arl=?,
                    document_type=?, blood_type=?, eps_reference_id=?, pension_fund_reference_id=?, arl_reference_id=?,
                    bank_name=?, bank_account=?, bank_reference_id=?, emergency_contact_name=?, emergency_contact_phone=?,
                    emergency_contact_relationship=?, education_level=?, marital_status=?, status=?, notes=?, updated_at=CURRENT_TIMESTAMP
                WHERE id = ? AND deleted_at IS NULL
                """,
                (
                    data["identification_number"].strip(), data["first_name"].strip(), data["last_name"].strip(),
                    data.get("email", "").strip() or None, data.get("phone", "").strip() or None,
                    data.get("position", "").strip() or None, data.get("hire_date") or None,
                    data.get("contract_end_date") or None, data.get("salary_type") or None,
                    data.get("pay_frequency") or "biweekly", data.get("base_salary") or 0, data.get("eps", "").strip() or None,
                    data.get("pension_fund", "").strip() or None, data.get("arl", "").strip() or None,
                    data.get("document_type", "").strip() or None, data.get("blood_type", "").strip() or None,
                    reference_id("eps", data.get("eps", "")), reference_id("pension_fund", data.get("pension_fund", "")),
                    reference_id("arl", data.get("arl", "")), data.get("bank_name", "").strip() or None,
                    data.get("bank_account", "").strip() or None, reference_id("bank", data.get("bank_name", "")),
                    data.get("emergency_contact_name", "").strip() or None, data.get("emergency_contact_phone", "").strip() or None,
                    data.get("emergency_contact_relationship", "").strip() or None, data.get("education_level", "").strip() or None,
                    data.get("marital_status", "").strip() or None, data.get("status", "active"),
                    data.get("notes", "").strip() or None, employee_id,
                ),
            )
            audit_event("update", "rrhh", "employees", employee_id, after={"position": data.get("position"), "status": data.get("status"), "base_salary": data.get("base_salary"), "eps": data.get("eps_reference_id"), "arl": data.get("arl_reference_id"), "pension_fund": data.get("pension_fund_reference_id"), "bank": data.get("bank_reference_id")})
            execute("UPDATE users SET employee_id=?, username=? WHERE employee_id=? OR username=?", (employee_id, data["identification_number"].strip(), employee_id, employee["identification_number"]))
            flash("Empleado actualizado.", "success")
            return redirect(url_for("employees.employee_list"))
        except sqlite3.IntegrityError:
            flash("La identificación ya existe o los datos no son válidos.", "danger")
    return render_template("employees/form.html", employee=employee, mode="employee")


@bp.get("/empleados/<int:employee_id>")
@login_required
def employee_profile(employee_id):
    employee = fetch_one(
        """SELECT e.*, COALESCE(eps_ref.name, e.eps) AS eps_display,
                  COALESCE(arl_ref.name, e.arl) AS arl_display,
                  COALESCE(pension_ref.name, e.pension_fund) AS pension_display,
                  COALESCE(bank_ref.name, e.bank_name) AS bank_display
           FROM employees e
           LEFT JOIN reference_items eps_ref ON eps_ref.id=e.eps_reference_id
           LEFT JOIN reference_items arl_ref ON arl_ref.id=e.arl_reference_id
           LEFT JOIN reference_items pension_ref ON pension_ref.id=e.pension_fund_reference_id
           LEFT JOIN reference_items bank_ref ON bank_ref.id=e.bank_reference_id
           WHERE e.id=? AND e.deleted_at IS NULL""", (employee_id,)
    )
    if employee is None:
        return render_template("error.html", code=404, message="Empleado no encontrado."), 404
    if not can_view_all_people() and employee["identification_number"] != g.user["username"]:
        return render_template("error.html", code=403, message="Solo puedes consultar tu propio perfil."), 403
    documents = fetch_all("""
        SELECT pd.*, pp.period_start, pp.period_end
        FROM payroll_documents pd LEFT JOIN payroll_periods pp ON pp.id=pd.payroll_period_id
        WHERE pd.employee_id=? AND pd.document_type='pay_stub'
        ORDER BY pd.uploaded_at DESC
    """, (employee_id,))
    return render_template("employees/profile.html", employee=employee, documents=documents, can_manage=can_manage_people(), can_view_all=can_view_all_people(), is_own_profile=employee["identification_number"] == g.user["username"])


@bp.get("/api/empleados/<int:employee_id>/contexto")
@login_required
def employee_context_api(employee_id):
    employee = fetch_one("""SELECT e.id, e.identification_number, e.first_name, e.last_name,
        e.document_type, e.position, e.hire_date, e.base_salary, e.pay_frequency,
        e.contract_end_date, e.status, COALESCE(eps.name, e.eps) AS eps,
        COALESCE(arl.name, e.arl) AS arl, COALESCE(pension.name, e.pension_fund) AS pension
        FROM employees e LEFT JOIN reference_items eps ON eps.id=e.eps_reference_id
        LEFT JOIN reference_items arl ON arl.id=e.arl_reference_id
        LEFT JOIN reference_items pension ON pension.id=e.pension_fund_reference_id
        WHERE e.id=? AND e.deleted_at IS NULL""", (employee_id,))
    if employee is None:
        return jsonify(error="Colaborador no encontrado"), 404
    if not can_view_all_people() and employee["identification_number"] != g.user["username"]:
        return jsonify(error="No autorizado"), 403
    return jsonify(dict(employee))


@bp.get("/mi-perfil")
@login_required
def my_profile():
    employee = current_employee()
    if employee is None:
        # Los usuarios administrativos pueden existir sin ser colaboradores
        # de nómina; deben tener igualmente un perfil de acceso funcional.
        if g.user and ({row["name"] for row in g.get("user_roles", [])} & {"admin", "gerencia", "rrhh", "asistente_administrativa"}):
            return render_template("employees/system_profile.html", user=g.user)
        return render_template("error.html", code=404, message="Tu usuario todavía no está vinculado a un perfil de colaborador."), 404
    return redirect(url_for("employees.employee_profile", employee_id=employee["id"]))


@bp.post("/empleados/<int:employee_id>/foto")
@login_required
def employee_photo_upload(employee_id):
    employee = fetch_one("SELECT id, identification_number FROM employees WHERE id=? AND deleted_at IS NULL", (employee_id,))
    if employee is None:
        return render_template("error.html", code=404, message="Empleado no encontrado."), 404
    if not can_manage_people() and employee["identification_number"] != g.user["username"]:
        return render_template("error.html", code=403, message="Solo puedes actualizar tu propia foto."), 403
    upload = request.files.get("photo")
    allowed = {"jpg", "jpeg", "png", "webp"}
    extension = (upload.filename.rsplit(".", 1)[-1].lower() if upload and upload.filename and "." in upload.filename else "")
    if not upload or extension not in allowed:
        flash("La foto debe estar en formato JPG, PNG o WEBP.", "danger")
        return redirect(url_for("employees.employee_profile", employee_id=employee_id))
    folder = Path(current_app.root_path) / "static" / "uploads" / "profiles"
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"employee-{employee_id}.{extension}"
    upload.save(folder / secure_filename(filename))
    execute("UPDATE employees SET profile_photo=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (filename, employee_id))
    audit_event("update_photo", "rrhh", "employees", employee_id, metadata={"filename": filename})
    flash("Foto de perfil actualizada.", "success")
    return redirect(url_for("employees.employee_profile", employee_id=employee_id))


@bp.post("/empleados/<int:employee_id>/eliminar")
@login_required
@roles_required("admin", "gerencia", "rrhh", "coordinador_operativo", "supervisor_operaciones")
def employee_delete(employee_id):
    if not delete_confirmation(request):
        flash("Debes confirmar la eliminación.", "warning")
    elif soft_delete_entity("employees", employee_id):
        flash("Empleado eliminado de forma lógica.", "success")
    else:
        flash("El empleado no existe o ya fue eliminado.", "warning")
    return redirect(url_for("employees.employee_list"))


@bp.get("/contratistas")
@login_required
def contractor_list():
    if not can_manage_people():
        return redirect(url_for("employees.my_profile"))
    contractors = fetch_all(
        "SELECT * FROM contractors WHERE deleted_at IS NULL ORDER BY legal_name"
    )
    return render_template("employees/list.html", contractors=contractors, mode="contractors", can_manage=can_manage_people())


@bp.route("/contratistas/nuevo", methods=("GET", "POST"))
@login_required
@roles_required("admin", "gerencia", "rrhh", "coordinador_operativo", "supervisor_operaciones")
def contractor_create():
    if request.method == "POST":
        data = request.form
        if not data.get("legal_name", "").strip() or not data.get("tax_id", "").strip():
            flash("Razón social y NIT son obligatorios.", "danger")
        else:
            try:
                execute(
                    """
                    INSERT INTO contractors (legal_name, tax_id, contact_name, email, phone,
                        service_type, contract_start_date, contract_end_date, status, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        data["legal_name"].strip(), data["tax_id"].strip(), data.get("contact_name", "").strip() or None,
                        data.get("email", "").strip() or None, data.get("phone", "").strip() or None,
                        data.get("service_type", "").strip() or None, data.get("contract_start_date") or None,
                        data.get("contract_end_date") or None, data.get("status", "active"), data.get("notes", "").strip() or None,
                    ),
                )
                flash("Contratista creado correctamente.", "success")
                return redirect(url_for("employees.contractor_list"))
            except sqlite3.IntegrityError:
                flash("El NIT ya existe o los datos no son válidos.", "danger")
    return render_template("employees/form.html", contractor=None, mode="contractor")


@bp.route("/contratistas/<int:contractor_id>/editar", methods=("GET", "POST"))
@login_required
@roles_required("admin", "gerencia", "rrhh", "coordinador_operativo", "supervisor_operaciones")
def contractor_edit(contractor_id):
    contractor = fetch_one("SELECT * FROM contractors WHERE id = ? AND deleted_at IS NULL", (contractor_id,))
    if contractor is None:
        return render_template("error.html", code=404, message="Contratista no encontrado."), 404
    if request.method == "POST":
        data = request.form
        try:
            execute(
                """
                UPDATE contractors SET legal_name=?, tax_id=?, contact_name=?, email=?, phone=?, service_type=?,
                    contract_start_date=?, contract_end_date=?, status=?, notes=?, updated_at=CURRENT_TIMESTAMP
                WHERE id = ? AND deleted_at IS NULL
                """,
                (
                    data["legal_name"].strip(), data["tax_id"].strip(), data.get("contact_name", "").strip() or None,
                    data.get("email", "").strip() or None, data.get("phone", "").strip() or None,
                    data.get("service_type", "").strip() or None, data.get("contract_start_date") or None,
                    data.get("contract_end_date") or None, data.get("status", "active"),
                    data.get("notes", "").strip() or None, contractor_id,
                ),
            )
            flash("Contratista actualizado.", "success")
            return redirect(url_for("employees.contractor_list"))
        except sqlite3.IntegrityError:
            flash("El NIT ya existe o los datos no son válidos.", "danger")
    return render_template("employees/form.html", contractor=contractor, mode="contractor")


@bp.post("/contratistas/<int:contractor_id>/eliminar")
@login_required
@roles_required("admin", "gerencia", "rrhh", "coordinador_operativo", "supervisor_operaciones")
def contractor_delete(contractor_id):
    if delete_confirmation(request) and soft_delete_entity("contractors", contractor_id):
        flash("Contratista eliminado de forma lógica.", "success")
    else:
        flash("Confirma la eliminación o verifica que el contratista exista.", "warning")
    return redirect(url_for("employees.contractor_list"))


@bp.get("/cuadrillas")
@login_required
def crew_list():
    user_roles = {row["name"] for row in g.get("user_roles", [])}
    if not can_manage_people() and "conductor" not in user_roles:
        return redirect(url_for("employees.my_profile"))
    scope = ""
    args = []
    if "supervisor_operaciones" in user_roles and not can_manage_people():
        supervisor = current_employee()
        scope = " AND c.supervisor_employee_id=?"
        args = [supervisor["id"] if supervisor else -1]
    elif "conductor" in user_roles and not can_manage_people():
        employee = current_employee()
        employee_id = employee["id"] if employee else -1
        scope = " AND EXISTS (SELECT 1 FROM crew_members cm2 WHERE cm2.crew_id=c.id AND cm2.employee_id=?)"
        args = [employee_id]
    crews = fetch_all(
        """
        SELECT c.*, e.first_name || ' ' || e.last_name AS supervisor_name, p.name AS project_name,
               (SELECT COUNT(*) FROM crew_members cm WHERE cm.crew_id = c.id) AS member_count
        FROM crews c LEFT JOIN employees e ON e.id = c.supervisor_employee_id LEFT JOIN projects p ON p.id=c.project_id
        WHERE c.deleted_at IS NULL""" + scope + " ORDER BY c.name", args
    )
    return render_template("employees/list.html", crews=crews, mode="crews", can_manage=can_manage_people())


@bp.route("/cuadrillas/nueva", methods=("GET", "POST"))
@login_required
@roles_required("admin", "gerencia", "coordinador_operativo")
def crew_create():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("El nombre de la cuadrilla es obligatorio.", "danger")
        else:
            try:
                with transaction():
                    crew_id = execute("INSERT INTO crews (name, supervisor_employee_id, project_id, status, notes) VALUES (?, ?, ?, ?, ?)", (name, request.form.get("supervisor_employee_id") or None, request.form.get("project_id") or None, request.form.get("status", "active"), request.form.get("notes", "").strip() or None)).lastrowid
                    for employee_id in request.form.getlist("employee_ids"):
                        execute("INSERT OR IGNORE INTO crew_members (crew_id, employee_id) VALUES (?, ?)", (crew_id, employee_id))
                    audit_event("create", "rrhh", "crews", crew_id, after={"name": name, "supervisor_employee_id": request.form.get("supervisor_employee_id"), "project_id": request.form.get("project_id"), "member_count": len(request.form.getlist("employee_ids"))})
                flash("Cuadrilla creada correctamente.", "success")
                return redirect(url_for("employees.crew_list"))
            except sqlite3.IntegrityError:
                flash("El nombre de la cuadrilla ya existe o el supervisor no es válido.", "danger")
    supervisors = fetch_all(
        "SELECT id, first_name || ' ' || last_name AS name FROM employees WHERE status='active' AND deleted_at IS NULL ORDER BY name"
    )
    projects = fetch_all("SELECT id, name, code FROM projects WHERE deleted_at IS NULL ORDER BY name")
    employees = fetch_all("SELECT id, first_name || ' ' || last_name AS name, position FROM employees WHERE status='active' AND deleted_at IS NULL ORDER BY name")
    return render_template("employees/crew_form.html", crew=None, supervisors=supervisors, projects=projects, employees=employees, members=[], mode="crew")


@bp.route("/cuadrillas/<int:crew_id>/editar", methods=("GET", "POST"))
@login_required
@roles_required("admin", "gerencia", "coordinador_operativo")
def crew_edit(crew_id):
    crew = fetch_one("SELECT * FROM crews WHERE id = ? AND deleted_at IS NULL", (crew_id,))
    if crew is None:
        return render_template("error.html", code=404, message="Cuadrilla no encontrada."), 404
    if request.method == "POST":
        try:
            with transaction():
                execute(
                    "UPDATE crews SET name=?, supervisor_employee_id=?, project_id=?, status=?, notes=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND deleted_at IS NULL",
                    (
                        request.form.get("name", "").strip(), request.form.get("supervisor_employee_id") or None,
                        request.form.get("project_id") or None, request.form.get("status", "active"), request.form.get("notes", "").strip() or None, crew_id,
                    ),
                )
                execute("DELETE FROM crew_members WHERE crew_id=?", (crew_id,))
                for employee_id in request.form.getlist("employee_ids"):
                    execute("INSERT OR IGNORE INTO crew_members (crew_id, employee_id) VALUES (?, ?)", (crew_id, employee_id))
                audit_event("update", "rrhh", "crews", crew_id, after={"name": request.form.get("name"), "supervisor_employee_id": request.form.get("supervisor_employee_id"), "project_id": request.form.get("project_id"), "member_count": len(request.form.getlist("employee_ids"))})
            flash("Cuadrilla actualizada.", "success")
            return redirect(url_for("employees.crew_list"))
        except sqlite3.IntegrityError:
            flash("El nombre ya existe o el supervisor no es válido.", "danger")
    supervisors = fetch_all(
        "SELECT id, first_name || ' ' || last_name AS name FROM employees WHERE status='active' AND deleted_at IS NULL ORDER BY name"
    )
    projects = fetch_all("SELECT id, name, code FROM projects WHERE deleted_at IS NULL ORDER BY name")
    employees = fetch_all("SELECT id, first_name || ' ' || last_name AS name, position FROM employees WHERE status='active' AND deleted_at IS NULL ORDER BY name")
    members = fetch_all("SELECT employee_id FROM crew_members WHERE crew_id=? AND employee_id IS NOT NULL", (crew_id,))
    return render_template("employees/crew_form.html", crew=crew, supervisors=supervisors, projects=projects, employees=employees, members=members, mode="crew")


@bp.post("/cuadrillas/<int:crew_id>/eliminar")
@login_required
@roles_required("admin", "gerencia", "coordinador_operativo")
def crew_delete(crew_id):
    if delete_confirmation(request) and soft_delete_entity("crews", crew_id):
        flash("Cuadrilla eliminada de forma lógica.", "success")
    else:
        flash("Confirma la eliminación o verifica que la cuadrilla exista.", "warning")
    return redirect(url_for("employees.crew_list"))
