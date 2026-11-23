import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import click
from flask import current_app, g


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    schema_path = Path(current_app.root_path).parent / "schema.sql"
    db.executescript(schema_path.read_text(encoding="utf-8"))
    apply_schema_extensions(db)
    from .reference_data import seed_reference_data
    seed_reference_data(db)
    db.commit()


def apply_schema_extensions(db):
    """Aplica cambios aditivos para instalaciones que ya tienen la base creada."""
    user_info = db.execute("PRAGMA table_info(users)").fetchall()
    user_columns = {row["name"] for row in user_info}
    if "username" not in user_columns:
        db.execute("ALTER TABLE users ADD COLUMN username TEXT")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username) WHERE username IS NOT NULL")
    if "failed_login_attempts" not in user_columns:
        db.execute("ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER NOT NULL DEFAULT 0")
    if "locked_until" not in user_columns:
        db.execute("ALTER TABLE users ADD COLUMN locked_until TEXT")
    if "must_change_password" not in user_columns:
        db.execute("ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0")
    if "employee_id" not in user_columns:
        db.execute("ALTER TABLE users ADD COLUMN employee_id INTEGER REFERENCES employees(id) ON DELETE SET NULL")
    # Las cuentas de colaboradores pueden autenticarse únicamente con documento.
    # Instalaciones antiguas tenían email NOT NULL; reconstruimos solo esa tabla,
    # conservando IDs, roles, auditoría y contraseñas.
    email_column = next((row for row in user_info if row["name"] == "email"), None)
    if email_column and email_column["notnull"]:
        db.commit()
        db.execute("PRAGMA foreign_keys=OFF")
        db.execute("""
            CREATE TABLE users_optional_email (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE COLLATE NOCASE,
                email TEXT UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                employee_id INTEGER REFERENCES employees(id) ON DELETE SET NULL,
                is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
                last_login_at TEXT,
                failed_login_attempts INTEGER NOT NULL DEFAULT 0,
                locked_until TEXT,
                must_change_password INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.execute("""
            INSERT INTO users_optional_email
            (id, username, email, password_hash, full_name, employee_id, is_active,
             last_login_at, failed_login_attempts, locked_until, must_change_password, created_at, updated_at)
            SELECT id, username, email, password_hash, full_name, employee_id, is_active,
                   last_login_at, failed_login_attempts, locked_until, must_change_password, created_at, updated_at
            FROM users
        """)
        db.execute("DROP TABLE users")
        db.execute("ALTER TABLE users_optional_email RENAME TO users")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username) WHERE username IS NOT NULL")
        db.commit()
        db.execute("PRAGMA foreign_keys=ON")
    crew_columns = {row["name"] for row in db.execute("PRAGMA table_info(crews)").fetchall()}
    if "project_id" not in crew_columns:
        db.execute("ALTER TABLE crews ADD COLUMN project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL")

    employee_columns = {row["name"] for row in db.execute("PRAGMA table_info(employees)").fetchall()}
    additions = {
        "document_type": "TEXT",
        "blood_type": "TEXT",
        "eps_reference_id": "INTEGER REFERENCES reference_items(id) ON DELETE SET NULL",
        "pension_fund_reference_id": "INTEGER REFERENCES reference_items(id) ON DELETE SET NULL",
        "arl_reference_id": "INTEGER REFERENCES reference_items(id) ON DELETE SET NULL",
        "bank_reference_id": "INTEGER REFERENCES reference_items(id) ON DELETE SET NULL",
        "emergency_contact_name": "TEXT",
        "emergency_contact_phone": "TEXT",
        "emergency_contact_relationship": "TEXT",
        "education_level": "TEXT",
        "marital_status": "TEXT",
        "profile_photo": "TEXT",
    }
    for name, definition in additions.items():
        if name not in employee_columns:
            db.execute(f"ALTER TABLE employees ADD COLUMN {name} {definition}")
    incident_columns = {row["name"] for row in db.execute("PRAGMA table_info(sst_incidents)").fetchall()}
    if incident_columns and "report_type" not in incident_columns:
        db.execute("ALTER TABLE sst_incidents ADD COLUMN report_type TEXT NOT NULL DEFAULT 'sst_incident'")
    if "pay_frequency" not in employee_columns:
        db.execute("ALTER TABLE employees ADD COLUMN pay_frequency TEXT NOT NULL DEFAULT 'biweekly'")
    payroll_columns = {row["name"] for row in db.execute("PRAGMA table_info(payroll_items)").fetchall()}
    payroll_additions = {
        "base_salary_amount": "NUMERIC NOT NULL DEFAULT 0",
        "total_base_amount": "NUMERIC NOT NULL DEFAULT 0",
        "biweekly_salary_amount": "NUMERIC NOT NULL DEFAULT 0",
        "transport_subsidy_amount": "NUMERIC NOT NULL DEFAULT 0",
        "overtime_amount": "NUMERIC NOT NULL DEFAULT 0",
        "other_earnings_amount": "NUMERIC NOT NULL DEFAULT 0",
    }
    for name, definition in payroll_additions.items():
        if name not in payroll_columns:
            db.execute(f"ALTER TABLE payroll_items ADD COLUMN {name} {definition}")
    equipment_columns = {row["name"] for row in db.execute("PRAGMA table_info(equipment)").fetchall()}
    for name, definition in {
        "assigned_driver_employee_id": "INTEGER REFERENCES employees(id) ON DELETE SET NULL",
        "vehicle_restrictions": "TEXT",
    }.items():
        if name not in equipment_columns:
            db.execute(f"ALTER TABLE equipment ADD COLUMN {name} {definition}")
    db.execute("""
        CREATE TABLE IF NOT EXISTS driver_employee_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            driver_employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
            employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
            project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (driver_employee_id, employee_id, project_id)
        )
    """)
    db.execute("""
        UPDATE users SET employee_id=(
            SELECT e.id FROM employees e
            WHERE e.identification_number=users.username
              AND e.deleted_at IS NULL
        )
        WHERE employee_id IS NULL AND username IS NOT NULL
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS payroll_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payroll_period_id INTEGER NOT NULL REFERENCES payroll_periods(id) ON DELETE CASCADE,
            employee_id INTEGER REFERENCES employees(id) ON DELETE SET NULL,
            document_type TEXT NOT NULL DEFAULT 'pay_stub' CHECK (document_type IN ('pay_stub', 'payroll_sheet')),
            original_name TEXT NOT NULL,
            stored_name TEXT NOT NULL UNIQUE,
            mime_type TEXT,
            uploaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (payroll_period_id, employee_id, document_type)
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS performance_evaluation_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evaluation_id INTEGER NOT NULL REFERENCES performance_evaluations(id) ON DELETE CASCADE,
            question_number INTEGER NOT NULL CHECK (question_number BETWEEN 1 AND 10),
            answer_score INTEGER NOT NULL CHECK (answer_score BETWEEN 1 AND 3),
            UNIQUE (evaluation_id, question_number)
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS document_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            original_name TEXT NOT NULL,
            stored_name TEXT NOT NULL UNIQUE,
            mime_type TEXT,
            field_mapping TEXT,
            uploaded_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1))
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS generated_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER NOT NULL REFERENCES document_templates(id) ON DELETE RESTRICT,
            employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
            original_name TEXT NOT NULL,
            stored_name TEXT NOT NULL UNIQUE,
            generated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    template_columns = {row["name"] for row in db.execute("PRAGMA table_info(document_templates)").fetchall()}
    if "field_mapping" not in template_columns:
        db.execute("ALTER TABLE document_templates ADD COLUMN field_mapping TEXT")
    audit_columns = {row["name"] for row in db.execute("PRAGMA table_info(audit_log)").fetchall()}
    audit_additions = {
        "module": "TEXT NOT NULL DEFAULT 'system'",
        "result": "TEXT NOT NULL DEFAULT 'success'",
        "reason": "TEXT",
        "before_json": "TEXT",
        "after_json": "TEXT",
        "correlation_id": "TEXT",
    }
    for name, definition in audit_additions.items():
        if name not in audit_columns:
            db.execute(f"ALTER TABLE audit_log ADD COLUMN {name} {definition}")
    db.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_entity ON audit_log(entity_type, entity_id, created_at)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_actor ON audit_log(user_id, created_at)")


@click.command("init-db")
def init_db_command():
    """Crea o actualiza las tablas del ERP."""
    init_db()
    click.echo("Base de datos inicializada.")


@click.command("backup-db")
@click.option("--destination", type=click.Path(file_okay=False, dir_okay=True), default=None)
def backup_db_command(destination):
    """Crea una copia consistente de SQLite usando el backup API."""
    source_path = Path(current_app.config["DATABASE"])
    if not source_path.exists():
        raise click.ClickException("La base de datos todavía no existe.")
    destination_dir = Path(destination) if destination else source_path.parent / "backups"
    destination_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = destination_dir / f"{source_path.stem}_{stamp}.db"
    source = sqlite3.connect(source_path)
    target = sqlite3.connect(backup_path)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    click.echo(f"Backup creado: {backup_path}")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(backup_db_command)


def fetch_one(query, args=()):
    return get_db().execute(query, args).fetchone()


def fetch_all(query, args=()):
    return get_db().execute(query, args).fetchall()


def execute(query, args=()):
    db = get_db()
    cursor = db.execute(query, args)
    if not g.get("transaction_depth"):
        db.commit()
    return cursor


@contextmanager
def transaction():
    """Atomic application transaction; audit events can join the same transaction."""
    db = get_db()
    depth = g.get("transaction_depth", 0)
    if depth == 0:
        db.execute("BEGIN")
    g.transaction_depth = depth + 1
    try:
        yield db
        g.transaction_depth -= 1
        if depth == 0:
            db.commit()
    except Exception:
        g.transaction_depth = depth
        if depth == 0:
            db.rollback()
        raise
