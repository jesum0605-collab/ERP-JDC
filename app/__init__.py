import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, g, jsonify, render_template, request

from .db import init_app, init_db
from .utils import csrf_token, validate_csrf


DEFAULT_SECRET_KEY = "dev-change-me"
PRODUCTION_ENVIRONMENTS = {"production", "prod"}


def create_app(test_config=None):
    load_dotenv()
    app = Flask(__name__, instance_relative_config=True)
    supplied_config = test_config or {}
    environment = str(
        supplied_config.get("APP_ENV")
        or os.getenv("APP_ENV")
        or os.getenv("FLASK_ENV")
        or "development"
    ).strip().lower()
    is_production = environment in PRODUCTION_ENVIRONMENTS
    secret_key = str(
        supplied_config.get("SECRET_KEY")
        if "SECRET_KEY" in supplied_config
        else os.getenv("SECRET_KEY", "")
    ).strip()
    if is_production and (not secret_key or secret_key == DEFAULT_SECRET_KEY):
        raise RuntimeError("SECRET_KEY debe estar configurada con un valor seguro en producción.")
    if not secret_key:
        secret_key = DEFAULT_SECRET_KEY
    app.config.from_mapping(
        APP_ENV=environment,
        SECRET_KEY=secret_key,
        DATABASE=os.getenv("DATABASE", str(Path(app.instance_path) / "jardines.db")),
        TELEMETRY_API_KEY=os.getenv("TELEMETRY_API_KEY", ""),
        DEBUG=False if is_production else os.getenv("FLASK_DEBUG", "0") == "1",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=True if is_production else os.getenv("SESSION_COOKIE_SECURE", "0") == "1",
    )
    if test_config:
        app.config.update(test_config)

    # Los NULL de SQLite deben mostrarse como campos vacíos, nunca como el texto "None".
    app.jinja_env.finalize = lambda value: "" if value is None else value

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)

    init_app(app)
    with app.app_context():
        init_db()

    # CSRF se aplica a formularios y endpoints de sesión. La telemetría usa API key.
    @app.before_request
    def protect_forms():
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            if request.endpoint in {"sst.receive_telemetry", "sst.receive_incident"}:
                return None
            if not validate_csrf():
                if request.is_json or request.path.startswith("/api/"):
                    return jsonify(error="CSRF token inválido"), 400
                return render_template("error.html", code=400, message="La solicitud de seguridad no es válida."), 400
        return None

    @app.context_processor
    def inject_helpers():
        def has_role(*roles):
            current = {row["name"] for row in g.get("user_roles", [])}
            if "operaciones" in roles:
                if current.intersection({"supervisor_operaciones", "coordinador_operativo"}):
                    current.add("operaciones")
            if "sst" in roles:
                if current.intersection({"supervisor_sst"}):
                    current.add("sst")
            return bool(current.intersection(roles)) or "admin" in current
        return {
            "csrf_token": csrf_token,
            "is_admin": bool(g.get("user") and any(row["name"] == "admin" for row in g.get("user_roles", []))),
            "has_role": has_role,
        }

    from .auth import bp as auth_bp, register_cli
    from .main import bp as main_bp
    from .employees import bp as employees_bp
    from .hr import bp as hr_bp
    from .admin import bp as admin_bp
    from .projects import bp as projects_bp
    from .resources import bp as resources_bp
    from .sst import bp as sst_bp
    from .api import bp as api_bp
    from .documents import bp as documents_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(employees_bp)
    app.register_blueprint(hr_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(resources_bp)
    app.register_blueprint(sst_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(documents_bp)
    register_cli(app)

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("error.html", code=404, message="La página solicitada no existe."), 404

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("error.html", code=403, message="No tienes permisos para realizar esta acción."), 403

    return app
