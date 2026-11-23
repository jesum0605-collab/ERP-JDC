from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse

import click
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .db import execute, fetch_all, fetch_one
from .utils import login_required

bp = Blueprint("auth", __name__)


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get("user_id")
    g.user = fetch_one("SELECT * FROM users WHERE id = ? AND is_active = 1", (user_id,)) if user_id else None
    g.user_roles = fetch_all(
        """
        SELECT r.name FROM roles r
        JOIN user_roles ur ON ur.role_id = r.id
        WHERE ur.user_id = ?
        """,
        (user_id,),
    ) if user_id else []


def is_safe_redirect(target):
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in {"http", "https"} and ref_url.netloc == test_url.netloc


def default_home_for(user_id):
    roles = {row["name"] for row in fetch_all("SELECT r.name FROM roles r JOIN user_roles ur ON ur.role_id=r.id WHERE ur.user_id=?", (user_id,))}
    if "conductor" in roles and not (roles & {"admin", "gerencia"}):
        return url_for("main.driver_home")
    if roles and roles <= {"jardinero"}:
        return url_for("main.worker_dashboard")
    return url_for("main.dashboard")


@bp.route("/login", methods=("GET", "POST"))
def login():
    if g.user:
        return redirect(default_home_for(g.user["id"]))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = fetch_one("SELECT * FROM users WHERE (email = ? OR username = ?) AND is_active = 1", (email, email))
        error = None
        now = datetime.now(timezone.utc)
        locked = False
        if user and user["locked_until"]:
            try:
                locked = datetime.fromisoformat(user["locked_until"]) > now
            except ValueError:
                locked = False
        if locked:
            error = "La cuenta está bloqueada temporalmente. Intenta de nuevo más tarde."
        elif user is None or not check_password_hash(user["password_hash"], password):
            error = "Correo o contraseña incorrectos."
            if user:
                attempts = int(user["failed_login_attempts"] or 0) + 1
                locked_until = None
                if attempts >= 5:
                    locked_until = (now + timedelta(minutes=15)).isoformat()
                execute(
                    "UPDATE users SET failed_login_attempts=?, locked_until=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (attempts, locked_until, user["id"]),
                )
        if error is None:
            session.clear()
            session["user_id"] = user["id"]
            execute(
                "UPDATE users SET last_login_at = ?, failed_login_attempts=0, locked_until=NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (now.isoformat(), user["id"]),
            )
            if user["must_change_password"]:
                flash("Tu contraseña es provisional. Debes cambiarla para continuar.", "warning")
                return redirect(url_for("auth.change_password"))
            next_url = request.args.get("next") or request.form.get("next")
            return redirect(next_url if is_safe_redirect(next_url) else default_home_for(user["id"]))
        flash(error, "danger")

    return render_template("auth/login.html")


@bp.post("/logout")
@login_required
def logout():
    session.clear()
    flash("Sesión cerrada.", "success")
    return redirect(url_for("auth.login"))


@bp.route("/mi-cuenta/contraseña", methods=("GET", "POST"))
@login_required
def change_password():
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirmation = request.form.get("confirmation", "")
        if not check_password_hash(g.user["password_hash"], current_password):
            flash("La contraseña actual no coincide.", "danger")
        elif len(new_password) < 10:
            flash("La nueva contraseña debe tener al menos 10 caracteres.", "danger")
        elif new_password != confirmation:
            flash("Las contraseñas nuevas no coinciden.", "danger")
        else:
            execute(
                "UPDATE users SET password_hash = ?, must_change_password = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (generate_password_hash(new_password), g.user["id"]),
            )
            flash("Contraseña actualizada correctamente.", "success")
            return redirect(url_for("main.dashboard"))
    return render_template("auth/change_password.html")


@click.command("create-admin")
@click.option("--email", prompt="Correo del administrador")
@click.option("--name", prompt="Nombre completo")
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
def create_admin_command(email, name, password):
    """Crea un usuario administrador inicial."""
    email = email.strip().lower()
    if len(password) < 12:
        raise click.ClickException("La contraseña debe tener al menos 12 caracteres.")
    if fetch_one("SELECT id FROM users WHERE email = ?", (email,)):
        raise click.ClickException("Ya existe un usuario con ese correo.")
    user_id = execute(
        "INSERT INTO users (email, password_hash, full_name) VALUES (?, ?, ?)",
        (email, generate_password_hash(password), name.strip()),
    ).lastrowid
    role_id = fetch_one("SELECT id FROM roles WHERE name = 'admin'")["id"]
    execute("INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)", (user_id, role_id))
    click.echo(f"Administrador creado: {email}")


def register_cli(app):
    app.cli.add_command(create_admin_command)
