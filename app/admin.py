import sqlite3

from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

from .db import execute, fetch_all, fetch_one
from .utils import audit_event, login_required, roles_required

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.get("/auditoria")
@login_required
@roles_required("admin", "gerencia")
def audit_list():
    events = fetch_all(
        """
        SELECT a.id, a.created_at, a.action, a.module, a.entity_type, a.entity_id,
               a.result, a.reason, a.correlation_id, u.full_name AS actor_name
        FROM audit_log a LEFT JOIN users u ON u.id=a.user_id
        ORDER BY a.created_at DESC, a.id DESC LIMIT 250
        """
    )
    return render_template("admin/audit.html", events=events)


def _admin_role_id():
    role = fetch_one("SELECT id FROM roles WHERE name='admin'")
    return str(role["id"]) if role else None


def _is_last_active_admin(user_id):
    row = fetch_one(
        """
        SELECT COUNT(*) AS total
        FROM users u
        JOIN user_roles ur ON ur.user_id=u.id
        JOIN roles r ON r.id=ur.role_id
        WHERE u.is_active=1 AND r.name='admin'
        """
    )
    current = fetch_one(
        """
        SELECT 1
        FROM users u
        JOIN user_roles ur ON ur.user_id=u.id
        JOIN roles r ON r.id=ur.role_id
        WHERE u.id=? AND u.is_active=1 AND r.name='admin'
        """,
        (user_id,),
    )
    return bool(current and row and row["total"] <= 1)


@bp.get("/usuarios")
@login_required
@roles_required("admin")
def users_list():
    search = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    users = fetch_all(
        """
        SELECT u.id, u.username, u.email, u.full_name, u.is_active, u.last_login_at,
               u.failed_login_attempts, u.locked_until,
               COALESCE(GROUP_CONCAT(r.name, ', '), '') AS role_names
        FROM users u LEFT JOIN user_roles ur ON ur.user_id=u.id
        LEFT JOIN roles r ON r.id=ur.role_id
        WHERE (? = '' OR u.full_name LIKE ? OR u.username LIKE ? OR u.email LIKE ? OR r.name LIKE ?)
          AND (? = '' OR (? = 'active' AND u.is_active=1) OR (? = 'inactive' AND u.is_active=0))
        GROUP BY u.id ORDER BY u.full_name
        """, (search, f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%", status, status, status)
    )
    roles = fetch_all("SELECT id, name, description FROM roles ORDER BY name")
    return render_template("admin/users.html", users=users, roles=roles)


@bp.route("/usuarios/nuevo", methods=("GET", "POST"))
@login_required
@roles_required("admin")
def user_create():
    roles = fetch_all("SELECT id, name, description FROM roles ORDER BY name")
    employees = fetch_all(
        """
        SELECT e.id, e.identification_number, e.first_name || ' ' || e.last_name AS name
        FROM employees e
        LEFT JOIN users u ON u.employee_id=e.id AND u.is_active=1
        WHERE e.status='active' AND e.deleted_at IS NULL AND u.id IS NULL
        ORDER BY e.last_name, e.first_name
        """
    )
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower() or None
        employee_id = request.form.get("employee_id") or None
        username = request.form.get("username", "").strip()
        full_name = request.form.get("full_name", "").strip()
        password = request.form.get("password", "")
        selected_roles = request.form.getlist("role_ids")
        employee = fetch_one("SELECT id, identification_number, first_name || ' ' || last_name AS name FROM employees WHERE id=? AND status='active' AND deleted_at IS NULL", (employee_id,)) if employee_id else None
        if employee:
            username = employee["identification_number"]
            full_name = full_name or employee["name"]
        elif not username and email:
            # Las cuentas vinculadas a colaboradores usan documento; las cuentas
            # técnicas sin colaborador pueden conservar el correo como acceso.
            username = email
        if not username or not full_name or len(password) < 12:
            flash("Selecciona un colaborador o indica un usuario, nombre y una contraseña de mínimo 12 caracteres.", "danger")
        elif not selected_roles:
            flash("Selecciona al menos un rol.", "danger")
        else:
            try:
                user_id = execute(
                    "INSERT INTO users (employee_id, username, email, password_hash, full_name, must_change_password) VALUES (?, ?, ?, ?, ?, 1)",
                    (employee["id"] if employee else None, username, email, generate_password_hash(password), full_name),
                ).lastrowid
                for role_id in selected_roles:
                    execute("INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)", (user_id, role_id))
                audit_event("create", "users", "users", user_id, after={"full_name": full_name, "employee_id": employee_id, "roles": selected_roles})
                flash("Usuario creado correctamente.", "success")
                return redirect(url_for("admin.users_list"))
            except sqlite3.IntegrityError:
                flash("El usuario, correo o colaborador ya tiene una cuenta, o alguno de los roles no es válido.", "danger")
    return render_template("admin/user_form.html", roles=roles, employees=employees)


@bp.post("/usuarios/<int:user_id>/roles")
@login_required
@roles_required("admin")
def user_roles_update(user_id):
    if not fetch_one("SELECT id FROM users WHERE id=?", (user_id,)):
        return render_template("error.html", code=404, message="Usuario no encontrado."), 404
    selected_roles = request.form.getlist("role_ids")
    if not selected_roles:
        flash("Cada usuario debe conservar al menos un rol.", "danger")
        return redirect(url_for("admin.users_list"))
    admin_role_id = _admin_role_id()
    if admin_role_id and admin_role_id not in selected_roles and _is_last_active_admin(user_id):
        flash("Debe existir al menos un administrador activo.", "warning")
        return redirect(url_for("admin.users_list"))
    before = [row["name"] for row in fetch_all("SELECT r.name FROM roles r JOIN user_roles ur ON ur.role_id=r.id WHERE ur.user_id=? ORDER BY r.name", (user_id,))]
    execute("DELETE FROM user_roles WHERE user_id=?", (user_id,))
    for role_id in selected_roles:
        execute("INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)", (user_id, role_id))
    after = [row["name"] for row in fetch_all("SELECT r.name FROM roles r JOIN user_roles ur ON ur.role_id=r.id WHERE ur.user_id=? ORDER BY r.name", (user_id,))]
    audit_event("update_roles", "users", "users", user_id, before={"roles": before}, after={"roles": after})
    flash("Roles actualizados.", "success")
    return redirect(url_for("admin.users_list"))


@bp.post("/usuarios/<int:user_id>/eliminar")
@login_required
@roles_required("admin")
def user_delete(user_id):
    if user_id == g.user["id"]:
        flash("No puedes eliminar tu propia cuenta.", "warning")
        return redirect(url_for("admin.users_list"))
    user = fetch_one("SELECT is_active FROM users WHERE id=?", (user_id,))
    if user is None:
        return render_template("error.html", code=404, message="Usuario no encontrado."), 404
    if user["is_active"] and _is_last_active_admin(user_id):
        flash("Debe existir al menos un administrador activo.", "warning")
    else:
        execute("UPDATE users SET is_active=0, updated_at=CURRENT_TIMESTAMP WHERE id=?", (user_id,))
        audit_event("deactivate", "users", "users", user_id, after={"is_active": 0})
        flash("Perfil eliminado de los accesos activos. El historial se conservó.", "success")
    return redirect(url_for("admin.users_list"))


@bp.route("/usuarios/<int:user_id>/restablecer-password", methods=("GET", "POST"))
@login_required
@roles_required("admin")
def user_password_reset(user_id):
    user = fetch_one("SELECT id, full_name, username FROM users WHERE id=? AND is_active=1", (user_id,))
    if request.method == "GET":
        if user is None:
            return render_template("error.html", code=404, message="Usuario no encontrado."), 404
        return render_template("admin/password_reset.html", user=user)
    password = request.form.get("new_password", "")
    if user is None:
        return render_template("error.html", code=404, message="Usuario no encontrado."), 404
    if len(password) < 10:
        flash("La nueva contraseña debe tener al menos 10 caracteres.", "danger")
    else:
        execute("UPDATE users SET password_hash=?, must_change_password=1, failed_login_attempts=0, locked_until=NULL, updated_at=CURRENT_TIMESTAMP WHERE id=?", (generate_password_hash(password), user_id))
        audit_event("reset_password", "users", "users", user_id, metadata={"must_change_password": True})
        flash("Contraseña restablecida por un administrador.", "success")
    return redirect(url_for("admin.users_list"))


@bp.post("/usuarios/<int:user_id>/estado")
@login_required
@roles_required("admin")
def user_status_update(user_id):
    if user_id == g.user["id"]:
        flash("No puedes desactivar tu propia cuenta.", "warning")
    else:
        user = fetch_one("SELECT is_active FROM users WHERE id=?", (user_id,))
        if user is None:
            return render_template("error.html", code=404, message="Usuario no encontrado."), 404
        if user["is_active"] and _is_last_active_admin(user_id):
            flash("Debe existir al menos un administrador activo.", "warning")
            return redirect(url_for("admin.users_list"))
        new_status = 0 if user["is_active"] else 1
        execute("UPDATE users SET is_active=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (new_status, user_id))
        audit_event("change_status", "users", "users", user_id, before={"is_active": user["is_active"]}, after={"is_active": new_status})
        flash("Estado del usuario actualizado.", "success")
    return redirect(url_for("admin.users_list"))
