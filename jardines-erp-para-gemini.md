# Jardines de la Costa S.A.S. - Codigo fuente para analisis`n`nEste documento agrupa el codigo fuente del ERP por ruta. No incluye base de datos, credenciales, binarios ni entorno virtual.`n

## ARCHIVO: .gitignore

``text
__pycache__/
*.py[cod]
.venv/
venv/
.env
instance/*.db
instance/*.db-*
*.pyc

``


## ARCHIVO: README.md

``text
# Jardines de la Costa S.A.S. · ERP inicial

Base ejecutable para un Sistema de Gestión Integral orientado a paisajismo y mantenimiento de construcción.

## Arquitectura

- **Backend:** Flask con patrón application factory y blueprints por módulo.
- **Persistencia:** SQLite con claves foráneas, índices, eliminación lógica y bitácora.
- **Frontend:** Jinja2, Bootstrap 5, Bootstrap Icons y CSS mobile-first.
- **API:** JSON para KPIs, dashboard SST y recepción de telemetría de campo.
- **Cruces y captura:** catálogos maestros SQLite reutilizables (EPS, ARL, sangre, pensiones, bancos, cargos, municipios y más), búsqueda por texto, autocompletado y contexto relacionado de proyectos/personas.
- **Reportes:** PDF mediante ReportLab.
- **Servicio:** WSGI compatible con Waitress; puede instalarse como servicio de Windows con NSSM.

## Puesta en marcha local

En PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
Copy-Item .env.example .env
flask --app run.py init-db
flask --app run.py create-admin
flask --app run.py run --host 0.0.0.0 --port 5000
```

Después abre `http://localhost:5000/login`.

En producción se debe cambiar `SECRET_KEY`, definir `TELEMETRY_API_KEY`, desactivar `FLASK_DEBUG` y proteger el servidor detrás de HTTPS/red privada.

## Pruebas y respaldos

Ejecuta las pruebas funcionales locales con el entorno virtual activo:

```powershell
py -m unittest discover -s tests -v
```

Para crear un respaldo consistente de SQLite:

```powershell
flask --app run.py backup-db
flask --app run.py backup-db --destination D:\respaldos\jardines
```

El comando genera un archivo con marca UTC y no modifica la base de datos de operación.

## Servicio de Windows

El punto de entrada WSGI es `wsgi:app`. Con Waitress:

```powershell
waitress-serve --listen=0.0.0.0:5000 wsgi:app
```

Para instalarlo como servicio se puede usar NSSM apuntando a:

- **Application:** `C:\ruta\al\proyecto\.venv\Scripts\waitress-serve.exe`
- **Arguments:** `--listen=0.0.0.0:5000 wsgi:app`
- **Startup directory:** la carpeta del proyecto

Configura las variables del archivo `.env` en el entorno del servicio y respalda periódicamente `instance/jardines.db`.

Para iniciar la instalación local con doble clic, usa `start_erp.cmd`. El lanzador utiliza el entorno `.venv` del proyecto y abre el servidor en `http://127.0.0.1:5000`.

## Telemetría de campo

El endpoint `POST /api/telemetry` recibe registros reales y los persiste en `telemetry_events`. Cuando `TELEMETRY_API_KEY` está definida, el dispositivo debe enviar el header `X-API-Key`.

Ejemplo de contrato de entrada:

```json
{
  "source_type": "gps_device",
  "device_id": "cuadrilla-07",
  "project_id": 1,
  "employee_id": 4,
  "event_type": "unsafe_condition",
  "severity": "medium",
  "latitude": 10.3910,
  "longitude": -75.4794,
  "occurred_at": "2026-10-22T14:30:00Z",
  "payload": {"helmet_detected": false}
}
```

## Rutas principales

| Área | Ruta |
|---|---|
| Dashboard | `/dashboard` |
| Personal | `/rrhh/empleados` |
| Contratistas | `/rrhh/contratistas` |
| Cuadrillas | `/rrhh/cuadrillas` |
| Nómina | `/rrhh/nomina` |
| Evaluación 9-Box | `/rrhh/evaluaciones-9box` |
| Proyectos | `/proyectos` |
| SST / HSE | `/sst` |
| Nueva inspección SST | `/sst/inspecciones/nueva` |
| Reportar incidente | `/sst/incidentes/nuevo` |
| Materiales | `/recursos/materiales` |
| Maquinaria | `/recursos/maquinaria` |
| Auditorías | `/recursos/auditorias` |
| KPIs JSON | `/api/kpis` |
| Dashboard SST JSON | `/api/sst/dashboard` |
| Catálogos de búsqueda | `/api/lookups/<employees|contractors|crews|projects|materials|equipment>` |
| Catálogos maestros | `/api/lookups/references/<catalog_code>` |
| Contexto relacionado | `/api/records/<project|employee>/<id>/context` |
| Telemetría de campo | `POST /api/telemetry` |
| Incidente de campo | `POST /api/sst/incidents` |
| Reporte PDF | `/reportes/kpis.pdf` |

## Alcance de esta iteración

Ya están disponibles las pantallas iniciales y rutas de escritura para nómina, aportes de seguridad social, evaluación 9-Box, inventario de materiales, programación de mantenimiento, auditorías y planes de acción. El cálculo de nómina usa tasas configurables en `app/hr.py`; debe ser revisado y parametrizado por contabilidad conforme al periodo y normativa aplicable antes de usarlo para pagos reales.

Los formularios SST y evaluación 9-Box ya usan búsqueda remota y muestran información relacionada al seleccionar un proyecto o empleado. Los selectores largos de otros formularios incorporan filtrado local automático.

La siguiente etapa puede incorporar permisos por acción más detallados, firma/aprobación de planillas, integración contable, carga documental y notificaciones automáticas.

``


## ARCHIVO: requirements.txt

``text
Flask>=3.0,<4.0
reportlab>=4.0,<5.0
pypdf>=5.0,<7.0
python-dotenv>=1.0,<2.0
waitress>=3.0,<4.0

``


## ARCHIVO: schema.sql

``text
PRAGMA foreign_keys = ON;

-- Jardines de la Costa S.A.S. - esquema inicial ERP
-- Todas las fechas se almacenan en UTC usando formato ISO-8601.

CREATE TABLE IF NOT EXISTS roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
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
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_roles (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);

-- Catálogos maestros para autocompletar y normalizar capturas.
CREATE TABLE IF NOT EXISTS reference_catalogs (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reference_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    catalog_code TEXT NOT NULL REFERENCES reference_catalogs(code) ON DELETE CASCADE,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    metadata_json TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    UNIQUE(catalog_code, code)
);

CREATE INDEX IF NOT EXISTS idx_reference_items_lookup
    ON reference_items(catalog_code, is_active, name);

CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identification_number TEXT NOT NULL UNIQUE,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    position TEXT,
    employment_type TEXT NOT NULL DEFAULT 'employee'
        CHECK (employment_type IN ('employee', 'contractor')),
    hire_date TEXT,
    contract_end_date TEXT,
    salary_type TEXT CHECK (salary_type IN ('monthly', 'daily', 'hourly', 'fee')),
    base_salary NUMERIC NOT NULL DEFAULT 0 CHECK (base_salary >= 0),
    bank_name TEXT,
    bank_account TEXT,
    eps TEXT,
    pension_fund TEXT,
    arl TEXT,
    document_type TEXT,
    blood_type TEXT,
    eps_reference_id INTEGER REFERENCES reference_items(id) ON DELETE SET NULL,
    pension_fund_reference_id INTEGER REFERENCES reference_items(id) ON DELETE SET NULL,
    arl_reference_id INTEGER REFERENCES reference_items(id) ON DELETE SET NULL,
    bank_reference_id INTEGER REFERENCES reference_items(id) ON DELETE SET NULL,
    emergency_contact_name TEXT,
    emergency_contact_phone TEXT,
    emergency_contact_relationship TEXT,
    education_level TEXT,
    marital_status TEXT,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive', 'suspended')),
    notes TEXT,
    profile_photo TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TEXT
);

CREATE TABLE IF NOT EXISTS contractors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    legal_name TEXT NOT NULL,
    tax_id TEXT NOT NULL UNIQUE,
    contact_name TEXT,
    email TEXT,
    phone TEXT,
    service_type TEXT,
    contract_start_date TEXT,
    contract_end_date TEXT,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive', 'suspended')),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TEXT
);

CREATE TABLE IF NOT EXISTS crews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    supervisor_employee_id INTEGER REFERENCES employees(id) ON DELETE SET NULL,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive')),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TEXT
);

CREATE TABLE IF NOT EXISTS crew_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    crew_id INTEGER NOT NULL REFERENCES crews(id) ON DELETE CASCADE,
    employee_id INTEGER REFERENCES employees(id) ON DELETE CASCADE,
    contractor_id INTEGER REFERENCES contractors(id) ON DELETE CASCADE,
    assigned_from TEXT,
    assigned_to TEXT,
    CHECK ((employee_id IS NOT NULL AND contractor_id IS NULL)
        OR (employee_id IS NULL AND contractor_id IS NOT NULL)),
    UNIQUE (crew_id, employee_id),
    UNIQUE (crew_id, contractor_id)
);

CREATE TABLE IF NOT EXISTS payroll_periods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    payment_date TEXT,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'calculated', 'paid', 'closed')),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (period_start, period_end)
);

CREATE TABLE IF NOT EXISTS payroll_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payroll_period_id INTEGER NOT NULL REFERENCES payroll_periods(id) ON DELETE CASCADE,
    employee_id INTEGER REFERENCES employees(id) ON DELETE SET NULL,
    contractor_id INTEGER REFERENCES contractors(id) ON DELETE SET NULL,
    gross_amount NUMERIC NOT NULL DEFAULT 0 CHECK (gross_amount >= 0),
    deductions NUMERIC NOT NULL DEFAULT 0 CHECK (deductions >= 0),
    net_amount NUMERIC NOT NULL DEFAULT 0 CHECK (net_amount >= 0),
    payment_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (payment_status IN ('pending', 'paid', 'rejected')),
    paid_at TEXT,
    CHECK ((employee_id IS NOT NULL AND contractor_id IS NULL)
        OR (employee_id IS NULL AND contractor_id IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS social_security_contributions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    employee_id INTEGER REFERENCES employees(id) ON DELETE SET NULL,
    contractor_id INTEGER REFERENCES contractors(id) ON DELETE SET NULL,
    eps_amount NUMERIC NOT NULL DEFAULT 0,
    pension_amount NUMERIC NOT NULL DEFAULT 0,
    arl_amount NUMERIC NOT NULL DEFAULT 0,
    caja_amount NUMERIC NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'reported', 'paid')),
    payment_reference TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK ((employee_id IS NOT NULL AND contractor_id IS NULL)
        OR (employee_id IS NULL AND contractor_id IS NOT NULL))
);

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
);

CREATE TABLE IF NOT EXISTS performance_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    evaluation_date TEXT NOT NULL,
    evaluator_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    performance_score INTEGER NOT NULL CHECK (performance_score BETWEEN 1 AND 3),
    potential_score INTEGER NOT NULL CHECK (potential_score BETWEEN 1 AND 3),
    nine_box_cell TEXT NOT NULL,
    strengths TEXT,
    development_plan TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS performance_evaluation_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evaluation_id INTEGER NOT NULL REFERENCES performance_evaluations(id) ON DELETE CASCADE,
    question_number INTEGER NOT NULL CHECK (question_number BETWEEN 1 AND 10),
    answer_score INTEGER NOT NULL CHECK (answer_score BETWEEN 1 AND 3),
    UNIQUE (evaluation_id, question_number)
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    client_name TEXT,
    client_contact TEXT,
    description TEXT,
    location TEXT,
    start_date TEXT,
    planned_end_date TEXT,
    actual_end_date TEXT,
    budget NUMERIC NOT NULL DEFAULT 0 CHECK (budget >= 0),
    status TEXT NOT NULL DEFAULT 'planning'
        CHECK (status IN ('planning', 'active', 'paused', 'completed', 'cancelled')),
    project_manager_employee_id INTEGER REFERENCES employees(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TEXT
);

CREATE TABLE IF NOT EXISTS project_phases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    sequence INTEGER NOT NULL DEFAULT 1,
    planned_start TEXT,
    planned_end TEXT,
    actual_start TEXT,
    actual_end TEXT,
    progress_percent NUMERIC NOT NULL DEFAULT 0 CHECK (progress_percent BETWEEN 0 AND 100),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'in_progress', 'blocked', 'completed')),
    UNIQUE (project_id, sequence)
);

CREATE TABLE IF NOT EXISTS project_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    employee_id INTEGER REFERENCES employees(id) ON DELETE SET NULL,
    contractor_id INTEGER REFERENCES contractors(id) ON DELETE SET NULL,
    crew_id INTEGER REFERENCES crews(id) ON DELETE SET NULL,
    role TEXT,
    assigned_from TEXT,
    assigned_to TEXT,
    CHECK ((employee_id IS NOT NULL) + (contractor_id IS NOT NULL) + (crew_id IS NOT NULL) = 1)
);

CREATE TABLE IF NOT EXISTS audits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    audit_type TEXT NOT NULL CHECK (audit_type IN ('operational', 'sst', 'quality', 'environmental')),
    audit_date TEXT NOT NULL,
    auditor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    score NUMERIC,
    findings TEXT,
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'in_progress', 'closed')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS action_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    audit_id INTEGER REFERENCES audits(id) ON DELETE CASCADE,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    responsible_employee_id INTEGER REFERENCES employees(id) ON DELETE SET NULL,
    due_date TEXT,
    completed_at TEXT,
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'in_progress', 'completed', 'overdue')),
    evidence_url TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    unit TEXT NOT NULL,
    minimum_stock NUMERIC NOT NULL DEFAULT 0,
    current_stock NUMERIC NOT NULL DEFAULT 0,
    unit_cost NUMERIC NOT NULL DEFAULT 0,
    supplier TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TEXT
);

CREATE TABLE IF NOT EXISTS inventory_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id INTEGER NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    movement_type TEXT NOT NULL CHECK (movement_type IN ('in', 'out', 'adjustment', 'return')),
    quantity NUMERIC NOT NULL CHECK (quantity > 0),
    unit_cost NUMERIC NOT NULL DEFAULT 0,
    reference TEXT,
    moved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS equipment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    equipment_type TEXT,
    brand TEXT,
    model TEXT,
    serial_number TEXT,
    status TEXT NOT NULL DEFAULT 'available'
        CHECK (status IN ('available', 'assigned', 'maintenance', 'out_of_service')),
    location TEXT,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    last_service_date TEXT,
    next_service_date TEXT,
    purchase_date TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TEXT
);

CREATE TABLE IF NOT EXISTS equipment_maintenance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_id INTEGER NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
    maintenance_type TEXT NOT NULL CHECK (maintenance_type IN ('preventive', 'corrective', 'inspection')),
    scheduled_date TEXT NOT NULL,
    completed_date TEXT,
    provider TEXT,
    cost NUMERIC NOT NULL DEFAULT 0,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'scheduled'
        CHECK (status IN ('scheduled', 'in_progress', 'completed', 'cancelled')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sst_inspections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    inspection_date TEXT NOT NULL,
    inspector_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    compliance_percent NUMERIC NOT NULL DEFAULT 0 CHECK (compliance_percent BETWEEN 0 AND 100),
    findings TEXT,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sst_incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    employee_id INTEGER REFERENCES employees(id) ON DELETE SET NULL,
    incident_type TEXT NOT NULL CHECK (incident_type IN ('near_miss', 'accident', 'illness', 'unsafe_condition')),
    severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    occurred_at TEXT NOT NULL,
    description TEXT NOT NULL,
    reported_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'investigating', 'closed')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sst_trainings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    training_date TEXT NOT NULL,
    facilitator TEXT,
    hours NUMERIC NOT NULL DEFAULT 0,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sst_training_attendees (
    training_id INTEGER NOT NULL REFERENCES sst_trainings(id) ON DELETE CASCADE,
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    attended INTEGER NOT NULL DEFAULT 1 CHECK (attended IN (0, 1)),
    PRIMARY KEY (training_id, employee_id)
);

CREATE TABLE IF NOT EXISTS telemetry_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    device_id TEXT,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    employee_id INTEGER REFERENCES employees(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'info'
        CHECK (severity IN ('info', 'low', 'medium', 'high', 'critical')),
    latitude NUMERIC,
    longitude NUMERIC,
    payload_json TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS kpi_definitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    unit TEXT,
    target NUMERIC,
    calculation_notes TEXT,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS kpi_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kpi_definition_id INTEGER NOT NULL REFERENCES kpi_definitions(id) ON DELETE CASCADE,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    value NUMERIC NOT NULL,
    calculated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (kpi_definition_id, period_start, period_end)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER,
    metadata_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_employees_status ON employees(status) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_contractors_status ON contractors(status) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_telemetry_occurred_at ON telemetry_events(occurred_at);
CREATE INDEX IF NOT EXISTS idx_telemetry_project ON telemetry_events(project_id);
CREATE INDEX IF NOT EXISTS idx_sst_incidents_occurred_at ON sst_incidents(occurred_at);
CREATE INDEX IF NOT EXISTS idx_equipment_next_service ON equipment(next_service_date);

INSERT OR IGNORE INTO roles (name, description) VALUES
    ('admin', 'Acceso total al sistema'),
    ('gerencia', 'Consulta de indicadores y gestión'),
    ('rrhh', 'Recursos humanos y nómina'),
    ('sst', 'Seguridad y salud en el trabajo'),
    ('supervisor_operaciones', 'Supervisión de operaciones y cuadrillas'),
    ('asistente_administrativa', 'Apoyo administrativo y consulta operativa'),
    ('coordinador_operativo', 'Coordinación operativa y administración del sistema'),
    ('supervisor_sst', 'Supervisión de seguridad y salud en el trabajo');
INSERT OR IGNORE INTO roles (name, description) VALUES ('conductor', 'Conducción, vehículos y apoyo logístico');

INSERT OR IGNORE INTO kpi_definitions (code, name, description, unit, target) VALUES
    ('ACTIVE_EMPLOYEES', 'Personal activo', 'Empleados y contratistas activos registrados', 'personas', NULL),
    ('ACTIVE_PROJECTS', 'Proyectos activos', 'Proyectos en ejecución', 'proyectos', NULL),
    ('SST_COMPLIANCE', 'Cumplimiento SST', 'Promedio de cumplimiento de inspecciones SST', '%', 90),
    ('OPEN_INCIDENTS', 'Incidentes abiertos', 'Incidentes SST pendientes de cierre', 'incidentes', 0),
    ('EQUIPMENT_AVAILABLE', 'Equipos disponibles', 'Equipos listos para asignación', 'equipos', NULL);

``


## ARCHIVO: wsgi.py

``text
from app import create_app

app = create_app()

``


## ARCHIVO: app\__init__.py

``text
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, g, jsonify, render_template, request

from .db import init_app, init_db
from .utils import csrf_token, validate_csrf


def create_app(test_config=None):
    load_dotenv()
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-change-me"),
        DATABASE=os.getenv("DATABASE", str(Path(app.instance_path) / "jardines.db")),
        TELEMETRY_API_KEY=os.getenv("TELEMETRY_API_KEY", ""),
        DEBUG=os.getenv("FLASK_DEBUG", "0") == "1",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "0") == "1",
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

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(employees_bp)
    app.register_blueprint(hr_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(resources_bp)
    app.register_blueprint(sst_bp)
    app.register_blueprint(api_bp)
    register_cli(app)

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("error.html", code=404, message="La página solicitada no existe."), 404

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("error.html", code=403, message="No tienes permisos para realizar esta acción."), 403

    return app

``


## ARCHIVO: app\admin.py

``text
import sqlite3

from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

from .db import execute, fetch_all, fetch_one
from .utils import login_required, roles_required

bp = Blueprint("admin", __name__, url_prefix="/admin")


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
        if not username or not full_name or len(password) < 12:
            flash("Selecciona un colaborador o indica un usuario, nombre y una contraseña de mínimo 12 caracteres.", "danger")
        elif not selected_roles:
            flash("Selecciona al menos un rol.", "danger")
        else:
            try:
                user_id = execute(
                    "INSERT INTO users (employee_id, username, email, password_hash, full_name) VALUES (?, ?, ?, ?, ?)",
                    (employee["id"] if employee else None, username, email, generate_password_hash(password), full_name),
                ).lastrowid
                for role_id in selected_roles:
                    execute("INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)", (user_id, role_id))
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
    execute("DELETE FROM user_roles WHERE user_id=?", (user_id,))
    for role_id in selected_roles:
        execute("INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)", (user_id, role_id))
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
        execute("UPDATE users SET password_hash=?, failed_login_attempts=0, locked_until=NULL, updated_at=CURRENT_TIMESTAMP WHERE id=?", (generate_password_hash(password), user_id))
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
        execute("UPDATE users SET is_active=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (0 if user["is_active"] else 1, user_id))
        flash("Estado del usuario actualizado.", "success")
    return redirect(url_for("admin.users_list"))

``


## ARCHIVO: app\api.py

``text
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

``


## ARCHIVO: app\auth.py

``text
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


@bp.route("/login", methods=("GET", "POST"))
def login():
    if g.user:
        return redirect(url_for("main.dashboard"))

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
            next_url = request.args.get("next") or request.form.get("next")
            return redirect(next_url if is_safe_redirect(next_url) else url_for("main.dashboard"))
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
                "UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
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

``


## ARCHIVO: app\db.py

``text
import sqlite3
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
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.execute("""
            INSERT INTO users_optional_email
            (id, username, email, password_hash, full_name, employee_id, is_active,
             last_login_at, failed_login_attempts, locked_until, created_at, updated_at)
            SELECT id, username, email, password_hash, full_name, employee_id, is_active,
                   last_login_at, failed_login_attempts, locked_until, created_at, updated_at
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
    db.commit()
    return cursor

``


## ARCHIVO: app\employees.py

``text
import sqlite3
from pathlib import Path

from flask import Blueprint, current_app, flash, g, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from .db import execute, fetch_all, fetch_one
from .utils import delete_confirmation, login_required, roles_required, soft_delete_entity

bp = Blueprint("employees", __name__, url_prefix="/rrhh")


MANAGER_ROLES = {"admin", "gerencia", "rrhh", "coordinador_operativo", "supervisor_operaciones"}
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
@roles_required("admin", "gerencia", "rrhh", "coordinador_operativo", "supervisor_operaciones")
def employee_create():
    if request.method == "POST":
        data = request.form
        required = [data.get("identification_number", "").strip(), data.get("first_name", "").strip(), data.get("last_name", "").strip()]
        if not all(required):
            flash("Identificación, nombres y apellidos son obligatorios.", "danger")
        else:
            try:
                execute(
                    """
                    INSERT INTO employees
                    (identification_number, first_name, last_name, email, phone, position,
                     hire_date, salary_type, base_salary, eps, pension_fund, arl, document_type, blood_type,
                     eps_reference_id, pension_fund_reference_id, arl_reference_id, bank_name, bank_account,
                     bank_reference_id, emergency_contact_name, emergency_contact_phone, emergency_contact_relationship,
                     education_level, marital_status, status, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        data["identification_number"].strip(), data["first_name"].strip(), data["last_name"].strip(),
                        data.get("email", "").strip() or None, data.get("phone", "").strip() or None,
                        data.get("position", "").strip() or None, data.get("hire_date") or None,
                        data.get("salary_type") or None, data.get("base_salary") or 0,
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
                )
                flash("Empleado creado correctamente.", "success")
                return redirect(url_for("employees.employee_list"))
            except sqlite3.IntegrityError:
                flash("La identificación ya existe o los datos no son válidos.", "danger")
    return render_template("employees/form.html", employee=None, mode="employee")


@bp.route("/empleados/<int:employee_id>/editar", methods=("GET", "POST"))
@login_required
@roles_required("admin", "gerencia", "rrhh", "coordinador_operativo", "supervisor_operaciones")
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
                    position=?, hire_date=?, contract_end_date=?, salary_type=?, base_salary=?, eps=?, pension_fund=?, arl=?,
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
                    data.get("base_salary") or 0, data.get("eps", "").strip() or None,
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


@bp.get("/mi-perfil")
@login_required
def my_profile():
    employee = current_employee()
    if employee is None:
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
    if not can_manage_people():
        return redirect(url_for("employees.my_profile"))
    crews = fetch_all(
        """
        SELECT c.*, e.first_name || ' ' || e.last_name AS supervisor_name, p.name AS project_name,
               (SELECT COUNT(*) FROM crew_members cm WHERE cm.crew_id = c.id) AS member_count
        FROM crews c LEFT JOIN employees e ON e.id = c.supervisor_employee_id LEFT JOIN projects p ON p.id=c.project_id
        WHERE c.deleted_at IS NULL ORDER BY c.name
        """
    )
    return render_template("employees/list.html", crews=crews, mode="crews", can_manage=can_manage_people())


@bp.route("/cuadrillas/nueva", methods=("GET", "POST"))
@login_required
@roles_required("admin", "gerencia", "operaciones")
def crew_create():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("El nombre de la cuadrilla es obligatorio.", "danger")
        else:
            try:
                crew_id = execute("INSERT INTO crews (name, supervisor_employee_id, project_id, status, notes) VALUES (?, ?, ?, ?, ?)", (name, request.form.get("supervisor_employee_id") or None, request.form.get("project_id") or None, request.form.get("status", "active"), request.form.get("notes", "").strip() or None)).lastrowid
                for employee_id in request.form.getlist("employee_ids"):
                    execute("INSERT OR IGNORE INTO crew_members (crew_id, employee_id) VALUES (?, ?)", (crew_id, employee_id))
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
@roles_required("admin", "gerencia", "operaciones")
def crew_edit(crew_id):
    crew = fetch_one("SELECT * FROM crews WHERE id = ? AND deleted_at IS NULL", (crew_id,))
    if crew is None:
        return render_template("error.html", code=404, message="Cuadrilla no encontrada."), 404
    if request.method == "POST":
        try:
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
@roles_required("admin", "gerencia", "operaciones")
def crew_delete(crew_id):
    if delete_confirmation(request) and soft_delete_entity("crews", crew_id):
        flash("Cuadrilla eliminada de forma lógica.", "success")
    else:
        flash("Confirma la eliminación o verifica que la cuadrilla exista.", "warning")
    return redirect(url_for("employees.crew_list"))

``


## ARCHIVO: app\hr.py

``text
import csv
import os
import re
from pathlib import Path
from datetime import date
from io import StringIO

from flask import Blueprint, Response, abort, current_app, flash, g, redirect, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

from .db import execute, fetch_all, fetch_one
from .utils import login_required, roles_required

bp = Blueprint("hr", __name__, url_prefix="/rrhh")

# Valores parametrizables para el cálculo inicial. Deben ser revisados por contabilidad
# antes de usar el sistema para liquidaciones legales reales.
SOCIAL_SECURITY_RATES = {
    "eps": 0.04,
    "pension": 0.04,
    "arl": 0.00522,
    "caja": 0.04,
}

NINE_BOX_LABELS = {
    (1, 1): "Bajo desempeño / Bajo potencial",
    (1, 2): "Bajo desempeño / Potencial medio",
    (1, 3): "Bajo desempeño / Alto potencial",
    (2, 1): "Desempeño medio / Bajo potencial",
    (2, 2): "Desempeño medio / Potencial medio",
    (2, 3): "Desempeño medio / Alto potencial",
    (3, 1): "Alto desempeño / Bajo potencial",
    (3, 2): "Alto desempeño / Potencial medio",
    (3, 3): "Alto desempeño / Alto potencial",
}
EVALUATION_QUESTIONS = [
    "Cumple los objetivos y entregables asignados", "Mantiene la calidad esperada en su trabajo",
    "Cumple normas de seguridad y procedimientos", "Trabaja efectivamente con el equipo", "Demuestra responsabilidad y autonomía",
    "Aprende rápidamente nuevas tareas", "Se adapta a cambios y nuevos retos", "Propone mejoras para la operación", "Puede asumir responsabilidades de liderazgo", "Tiene proyección para crecer dentro de la empresa",
]


@bp.get("/nomina")
@login_required
@roles_required("admin", "gerencia", "rrhh", "asistente_administrativa", "coordinador_operativo")
def payroll_list():
    periods = fetch_all(
        """
        SELECT pp.*, COUNT(pi.id) AS item_count,
               COALESCE(SUM(pi.net_amount), 0) AS total_net
        FROM payroll_periods pp
        LEFT JOIN payroll_items pi ON pi.payroll_period_id = pp.id
        GROUP BY pp.id ORDER BY pp.period_start DESC
        """
    )
    return render_template("hr/payroll_list.html", periods=periods)


@bp.route("/nomina/nueva", methods=("GET", "POST"))
@login_required
@roles_required("admin", "gerencia", "rrhh", "asistente_administrativa", "coordinador_operativo")
def payroll_create():
    if request.method == "POST":
        start = request.form.get("period_start")
        end = request.form.get("period_end")
        if not start or not end or start > end:
            flash("El rango de fechas de la nómina no es válido.", "danger")
        else:
            try:
                period_id = execute(
                    "INSERT INTO payroll_periods (period_start, period_end, payment_date, notes) VALUES (?, ?, ?, ?)",
                    (start, end, request.form.get("payment_date") or None, request.form.get("notes", "").strip() or None),
                ).lastrowid
                flash("Periodo de nómina creado. Ahora puedes calcularlo.", "success")
                return redirect(url_for("hr.payroll_detail", period_id=period_id))
            except Exception:
                flash("El periodo ya existe o los datos no son válidos.", "danger")
    return render_template("hr/payroll_form.html")


@bp.get("/nomina/<int:period_id>")
@login_required
@roles_required("admin", "gerencia", "rrhh", "asistente_administrativa", "coordinador_operativo")
def payroll_detail(period_id):
    period = fetch_one("SELECT * FROM payroll_periods WHERE id = ?", (period_id,))
    if period is None:
        return render_template("error.html", code=404, message="Periodo de nómina no encontrado."), 404
    items = fetch_all(
        """
        SELECT pi.*, e.first_name || ' ' || e.last_name AS employee_name, e.identification_number
        FROM payroll_items pi LEFT JOIN employees e ON e.id = pi.employee_id
        WHERE pi.payroll_period_id = ? ORDER BY employee_name
        """,
        (period_id,),
    )
    contributions = fetch_all(
        """
        SELECT ssc.*, e.first_name || ' ' || e.last_name AS employee_name,
               COALESCE(eps_ref.name, e.eps, 'No registrada') AS eps_name,
               COALESCE(pension_ref.name, e.pension_fund, 'No registrada') AS pension_name,
               COALESCE(arl_ref.name, e.arl, 'No registrada') AS arl_name
        FROM social_security_contributions ssc
        LEFT JOIN employees e ON e.id = ssc.employee_id
        LEFT JOIN reference_items eps_ref ON eps_ref.id=e.eps_reference_id
        LEFT JOIN reference_items pension_ref ON pension_ref.id=e.pension_fund_reference_id
        LEFT JOIN reference_items arl_ref ON arl_ref.id=e.arl_reference_id
        WHERE ssc.period_start = ? AND ssc.period_end = ? ORDER BY employee_name
        """,
        (period["period_start"], period["period_end"]),
    )
    totals = {
        "gross": sum(float(item["gross_amount"] or 0) for item in items),
        "deductions": sum(float(item["deductions"] or 0) for item in items),
        "net": sum(float(item["net_amount"] or 0) for item in items),
    }
    documents = fetch_all("""
        SELECT pd.*, e.first_name || ' ' || e.last_name AS employee_name
        FROM payroll_documents pd LEFT JOIN employees e ON e.id = pd.employee_id
        WHERE pd.payroll_period_id = ? ORDER BY pd.uploaded_at DESC
    """, (period_id,))
    return render_template("hr/payroll_detail.html", period=period, items=items, contributions=contributions, totals=totals, documents=documents)


@bp.post("/nomina/<int:period_id>/importar-planilla")
@login_required
@roles_required("admin", "gerencia", "rrhh", "asistente_administrativa", "coordinador_operativo")
def payroll_import(period_id):
    period = fetch_one("SELECT * FROM payroll_periods WHERE id = ?", (period_id,))
    upload = request.files.get("planilla")
    if period is None:
        return render_template("error.html", code=404, message="Periodo de nómina no encontrado."), 404
    if not upload or not upload.filename.lower().endswith(".csv"):
        flash("Selecciona una planilla CSV válida.", "danger")
        return redirect(url_for("hr.payroll_detail", period_id=period_id))
    try:
        content = upload.stream.read().decode("utf-8-sig")
        reader = csv.DictReader(StringIO(content))
        required = {"identificacion", "devengado", "deducciones", "neto"}
        headers = {str(h or "").strip().lower().replace(" ", "_") for h in (reader.fieldnames or [])}
        if not required.issubset(headers):
            raise ValueError("La planilla debe incluir identificacion, devengado, deducciones y neto.")
        imported = 0
        for row in reader:
            normalized = {str(k or "").strip().lower().replace(" ", "_"): (v or "").strip() for k, v in row.items()}
            employee = fetch_one("SELECT id FROM employees WHERE identification_number = ? AND deleted_at IS NULL", (normalized["identificacion"],))
            if employee is None:
                continue
            execute("""
                INSERT INTO payroll_items (payroll_period_id, employee_id, gross_amount, deductions, net_amount, payment_status)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT DO NOTHING
            """, (period_id, employee["id"], float(normalized["devengado"] or 0), float(normalized["deducciones"] or 0), float(normalized["neto"] or 0), normalized.get("estado", "pending") or "pending"))
            imported += 1
        execute("UPDATE payroll_periods SET status='calculated' WHERE id=?", (period_id,))
        flash(f"Planilla importada: {imported} registros asociados por identificación.", "success")
    except (ValueError, UnicodeDecodeError) as error:
        flash(f"No se pudo importar la planilla: {error}", "danger")
    return redirect(url_for("hr.payroll_detail", period_id=period_id))


@bp.post("/nomina/<int:period_id>/volantes")
@login_required
@roles_required("admin", "gerencia", "rrhh", "asistente_administrativa", "coordinador_operativo")
def payroll_upload_slip(period_id):
    period = fetch_one("SELECT * FROM payroll_periods WHERE id = ?", (period_id,))
    employee_id = request.form.get("employee_id")
    upload = request.files.get("volante")
    if period is None:
        return render_template("error.html", code=404, message="Periodo de nómina no encontrado."), 404
    if not upload or not employee_id or not upload.filename.lower().endswith(".pdf"):
        flash("Selecciona un empleado y un volante PDF válido.", "danger")
        return redirect(url_for("hr.payroll_detail", period_id=period_id))
    folder = Path(current_app.instance_path) / "payroll_documents"
    folder.mkdir(parents=True, exist_ok=True)
    stored = f"{period_id}_{employee_id}_{secure_filename(upload.filename)}"
    upload.save(folder / stored)
    execute("DELETE FROM payroll_documents WHERE payroll_period_id=? AND employee_id=? AND document_type='pay_stub'", (period_id, employee_id))
    execute("""INSERT INTO payroll_documents (payroll_period_id, employee_id, document_type, original_name, stored_name, mime_type)
              VALUES (?, ?, 'pay_stub', ?, ?, 'application/pdf')""", (period_id, employee_id, upload.filename, stored))
    flash("Volante de pago cargado correctamente.", "success")
    return redirect(url_for("hr.payroll_detail", period_id=period_id))


@bp.post("/nomina/<int:period_id>/volantes-consolidados")
@login_required
@roles_required("admin", "gerencia", "rrhh", "asistente_administrativa", "coordinador_operativo")
def payroll_upload_consolidated_slips(period_id):
    period = fetch_one("SELECT * FROM payroll_periods WHERE id = ?", (period_id,))
    upload = request.files.get("volantes_consolidados")
    if period is None:
        return render_template("error.html", code=404, message="Periodo de nómina no encontrado."), 404
    if not upload or not upload.filename.lower().endswith(".pdf"):
        flash("Selecciona un PDF consolidado válido.", "danger")
        return redirect(url_for("hr.payroll_detail", period_id=period_id))
    folder = Path(current_app.instance_path) / "payroll_documents"
    folder.mkdir(parents=True, exist_ok=True)
    if request.form.get("distribute") == "1":
        try:
            import PIL
            if not getattr(PIL, "__version__", None):
                PIL.__version__ = "13.0.0"
            from pypdf import PdfReader, PdfWriter
            from copy import deepcopy
        except ImportError:
            flash("Falta instalar el componente PDF para distribuir automáticamente los volantes.", "danger")
            return redirect(url_for("hr.payroll_detail", period_id=period_id))
        source = folder / f"_source_{secure_filename(upload.filename)}"
        upload.save(source)
        distributed = unmatched = 0
        reader = PdfReader(str(source))
        execute("DELETE FROM payroll_documents WHERE payroll_period_id=? AND document_type='pay_stub'", (period_id,))
        for page_number, original_page in enumerate(reader.pages):
            width, height = float(original_page.mediabox.width), float(original_page.mediabox.height)
            page_text = original_page.extract_text() or ""
            page_ids = re.findall(r"C\.?C\.?\s*#?\s*([0-9][0-9. ]{4,})", page_text, re.I)
            for block, (bottom, top) in enumerate(((height / 2, height), (0, height / 2)), start=1):
                page = deepcopy(original_page)
                page.cropbox.lower_left = (0, bottom)
                page.cropbox.upper_right = (width, top)
                identification = re.sub(r"\D", "", page_ids[block - 1]) if len(page_ids) >= block else ""
                employee = fetch_one("SELECT id FROM employees WHERE replace(replace(identification_number, '.', ''), ' ', '') = ? AND deleted_at IS NULL", (identification,)) if identification else None
                if employee is None:
                    unmatched += 1
                    continue
                stored = f"{period_id}_{employee['id']}_volante_{page_number + 1}_{block}.pdf"
                writer = PdfWriter(); writer.add_page(page)
                with open(folder / stored, "wb") as output:
                    writer.write(output)
                execute("DELETE FROM payroll_documents WHERE payroll_period_id=? AND employee_id=? AND document_type='pay_stub'", (period_id, employee["id"]))
                execute("INSERT INTO payroll_documents (payroll_period_id, employee_id, document_type, original_name, stored_name, mime_type) VALUES (?, ?, 'pay_stub', ?, ?, 'application/pdf')", (period_id, employee["id"], f"Volante página {page_number + 1}-{block}.pdf", stored))
                distributed += 1
        try: source.unlink()
        except OSError: pass
        flash(f"Distribución terminada: {distributed} volantes asociados. {unmatched} bloques requieren revisión.", "success" if distributed else "warning")
        return redirect(url_for("hr.payroll_detail", period_id=period_id))
    stored = f"{period_id}_consolidado_{secure_filename(upload.filename)}"
    upload.save(folder / stored)
    execute("DELETE FROM payroll_documents WHERE payroll_period_id=? AND document_type='payroll_sheet'", (period_id,))
    execute("""INSERT INTO payroll_documents (payroll_period_id, employee_id, document_type, original_name, stored_name, mime_type)
              VALUES (?, NULL, 'payroll_sheet', ?, ?, 'application/pdf')""", (period_id, upload.filename, stored))
    flash("Volantes consolidados cargados correctamente para todo el periodo.", "success")
    return redirect(url_for("hr.payroll_detail", period_id=period_id))


@bp.get("/nomina/documentos/<int:document_id>")
@login_required
def payroll_document(document_id):
    document = fetch_one("SELECT pd.*, e.identification_number FROM payroll_documents pd LEFT JOIN employees e ON e.id=pd.employee_id WHERE pd.id=?", (document_id,))
    if document is None:
        return render_template("error.html", code=404, message="Documento no encontrado."), 404
    manager_roles = {"admin", "gerencia", "rrhh", "asistente_administrativa", "coordinador_operativo"}
    current_roles = {row["name"] for row in g.get("user_roles", [])}
    if not current_roles.intersection(manager_roles) and document["identification_number"] != g.user["username"]:
        abort(403)
    return send_from_directory(Path(current_app.instance_path) / "payroll_documents", document["stored_name"], as_attachment=False, download_name=document["original_name"])


@bp.post("/nomina/<int:period_id>/eliminar-corte")
@login_required
@roles_required("admin", "gerencia", "rrhh", "asistente_administrativa", "coordinador_operativo")
def payroll_delete_cut(period_id):
    documents = fetch_all("SELECT stored_name FROM payroll_documents WHERE payroll_period_id=? AND document_type='pay_stub'", (period_id,))
    folder = Path(current_app.instance_path) / "payroll_documents"
    for document in documents:
        try:
            (folder / document["stored_name"]).unlink()
        except OSError:
            pass
    execute("DELETE FROM payroll_documents WHERE payroll_period_id=? AND document_type='pay_stub'", (period_id,))
    flash(f"Corte eliminado. Se retiraron {len(documents)} volantes individuales; el PDF consolidado se conservó.", "success")
    return redirect(url_for("hr.payroll_detail", period_id=period_id))


@bp.post("/nomina/<int:period_id>/calcular")
@login_required
@roles_required("admin", "gerencia", "rrhh", "asistente_administrativa", "coordinador_operativo")
def payroll_calculate(period_id):
    period = fetch_one("SELECT * FROM payroll_periods WHERE id = ?", (period_id,))
    if period is None:
        return render_template("error.html", code=404, message="Periodo de nómina no encontrado."), 404
    start = date.fromisoformat(period["period_start"])
    end = date.fromisoformat(period["period_end"])
    days = (end - start).days + 1
    employees = fetch_all(
        "SELECT * FROM employees WHERE status='active' AND deleted_at IS NULL ORDER BY last_name, first_name"
    )
    execute("DELETE FROM payroll_items WHERE payroll_period_id = ?", (period_id,))
    execute(
        "DELETE FROM social_security_contributions WHERE period_start = ? AND period_end = ?",
        (period["period_start"], period["period_end"]),
    )
    for employee in employees:
        base = float(employee["base_salary"] or 0)
        salary_type = employee["salary_type"] or "monthly"
        if salary_type == "daily":
            gross = base * min(days, 30)
        elif salary_type == "hourly":
            gross = base * min(days, 30) * 8
        else:
            gross = base
        eps = round(gross * SOCIAL_SECURITY_RATES["eps"], 2)
        pension = round(gross * SOCIAL_SECURITY_RATES["pension"], 2)
        arl = round(gross * SOCIAL_SECURITY_RATES["arl"], 2)
        caja = round(gross * SOCIAL_SECURITY_RATES["caja"], 2)
        deductions = round(eps + pension, 2)
        execute(
            """
            INSERT INTO payroll_items
            (payroll_period_id, employee_id, gross_amount, deductions, net_amount, payment_status)
            VALUES (?, ?, ?, ?, ?, 'pending')
            """,
            (period_id, employee["id"], gross, deductions, round(gross - deductions, 2)),
        )
        execute(
            """
            INSERT INTO social_security_contributions
            (period_start, period_end, employee_id, eps_amount, pension_amount, arl_amount, caja_amount)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (period["period_start"], period["period_end"], employee["id"], eps, pension, arl, caja),
        )
    execute("UPDATE payroll_periods SET status='calculated' WHERE id = ?", (period_id,))
    flash(f"Nómina calculada para {len(employees)} empleados activos.", "success")
    return redirect(url_for("hr.payroll_detail", period_id=period_id))


@bp.post("/nomina/<int:period_id>/cerrar")
@login_required
@roles_required("admin", "gerencia", "rrhh", "asistente_administrativa", "coordinador_operativo")
def payroll_close(period_id):
    execute("UPDATE payroll_periods SET status='closed' WHERE id = ? AND status='calculated'", (period_id,))
    flash("Periodo de nómina cerrado.", "success")
    return redirect(url_for("hr.payroll_detail", period_id=period_id))


@bp.get("/nomina/<int:period_id>/planilla.csv")
@login_required
@roles_required("admin", "gerencia", "rrhh", "asistente_administrativa", "coordinador_operativo")
def payroll_social_security_csv(period_id):
    period = fetch_one("SELECT * FROM payroll_periods WHERE id=?", (period_id,))
    if period is None:
        return render_template("error.html", code=404, message="Periodo de nómina no encontrado."), 404
    rows = fetch_all(
        """
        SELECT e.identification_number, e.first_name || ' ' || e.last_name AS employee_name,
               COALESCE(eps_ref.name, e.eps, '') AS eps_name,
               COALESCE(pension_ref.name, e.pension_fund, '') AS pension_name,
               COALESCE(arl_ref.name, e.arl, '') AS arl_name,
               ssc.eps_amount, ssc.pension_amount,
               ssc.arl_amount, ssc.caja_amount, ssc.status
        FROM social_security_contributions ssc
        JOIN employees e ON e.id=ssc.employee_id
        LEFT JOIN reference_items eps_ref ON eps_ref.id=e.eps_reference_id
        LEFT JOIN reference_items pension_ref ON pension_ref.id=e.pension_fund_reference_id
        LEFT JOIN reference_items arl_ref ON arl_ref.id=e.arl_reference_id
        WHERE ssc.period_start=? AND ssc.period_end=?
        ORDER BY employee_name
        """,
        (period["period_start"], period["period_end"]),
    )
    output = StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow([
        "Identificación", "Empleado", "EPS", "Fondo pensión", "ARL",
        "Aporte EPS", "Aporte pensión", "Aporte ARL", "Caja", "Estado",
    ])
    for row in rows:
        writer.writerow([
            row["identification_number"], row["employee_name"], row["eps_name"] or "",
            row["pension_name"] or "", row["arl_name"] or "", row["eps_amount"],
            row["pension_amount"], row["arl_amount"], row["caja_amount"], row["status"],
        ])
    filename = f"planilla-seguridad-social-{period['period_start']}-{period['period_end']}.csv"
    return Response(
        output.getvalue(), mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@bp.get("/evaluaciones-9box")
@login_required
@roles_required("admin", "gerencia", "rrhh", "coordinador_operativo", "supervisor_operaciones")
def evaluation_list():
    evaluations = fetch_all(
        """
        SELECT pe.*, e.first_name || ' ' || e.last_name AS employee_name,
               u.full_name AS evaluator_name
        FROM performance_evaluations pe
        JOIN employees e ON e.id = pe.employee_id
        LEFT JOIN users u ON u.id = pe.evaluator_user_id
        ORDER BY pe.evaluation_date DESC, employee_name
        """
    )
    return render_template("hr/evaluations.html", evaluations=evaluations, labels=NINE_BOX_LABELS)


@bp.route("/evaluaciones-9box/nueva", methods=("GET", "POST"))
@login_required
@roles_required("admin", "gerencia", "rrhh", "coordinador_operativo", "supervisor_operaciones")
def evaluation_create():
    employees = fetch_all(
        "SELECT id, first_name || ' ' || last_name AS name, position FROM employees WHERE status='active' AND deleted_at IS NULL ORDER BY name"
    )
    if request.method == "POST":
        answers = [int(request.form.get(f"question_{i}", 0)) for i in range(1, 11)]
        performance = round(sum(answers[:5]) / 5) if all(1 <= value <= 3 for value in answers) else 0
        potential = round(sum(answers[5:]) / 5) if all(1 <= value <= 3 for value in answers) else 0
        if performance not in (1, 2, 3) or potential not in (1, 2, 3):
            flash("El desempeño y el potencial deben estar entre 1 y 3.", "danger")
        else:
            cell = NINE_BOX_LABELS[(performance, potential)]
            created = execute(
                """
                INSERT INTO performance_evaluations
                (employee_id, evaluation_date, evaluator_user_id, performance_score, potential_score,
                 nine_box_cell, strengths, development_plan)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request.form.get("employee_id"), request.form.get("evaluation_date") or date.today().isoformat(),
                    g.user["id"], performance, potential, cell,
                    request.form.get("strengths", "").strip() or None,
                    request.form.get("development_plan", "").strip() or None,
                ),
            )
            for number, score in enumerate(answers, 1):
                execute("INSERT INTO performance_evaluation_answers (evaluation_id, question_number, answer_score) VALUES (?, ?, ?)", (created.lastrowid, number, score))
            flash("Evaluación 9-Box registrada.", "success")
            return redirect(url_for("hr.evaluation_list"))
    return render_template("hr/evaluation_form.html", employees=employees, evaluation_questions=EVALUATION_QUESTIONS)

``


## ARCHIVO: app\main.py

``text
from flask import Blueprint, g, render_template

from .db import fetch_all, fetch_one
from .utils import login_required

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
    metrics = {
        "active_people": fetch_one(
            "SELECT COUNT(*) AS total FROM employees WHERE status = 'active' AND deleted_at IS NULL"
        )["total"]
        + fetch_one("SELECT COUNT(*) AS total FROM contractors WHERE status = 'active' AND deleted_at IS NULL")["total"],
        "active_projects": fetch_one(
            "SELECT COUNT(*) AS total FROM projects WHERE status = 'active' AND deleted_at IS NULL"
        )["total"],
        "open_incidents": fetch_one(
            "SELECT COUNT(*) AS total FROM sst_incidents WHERE status <> 'closed'"
        )["total"],
        "equipment_due": fetch_one(
            """
            SELECT COUNT(*) AS total FROM equipment
            WHERE deleted_at IS NULL
              AND next_service_date IS NOT NULL
              AND date(next_service_date) <= date('now', '+30 day')
            """
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
        FROM projects
        WHERE deleted_at IS NULL
        ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END, planned_end_date IS NULL, planned_end_date
        LIMIT 8
        """
    )
    recent_telemetry = fetch_all(
        """
        SELECT event_type, severity, source_type, occurred_at
        FROM telemetry_events
        ORDER BY received_at DESC
        LIMIT 6
        """
    )
    return render_template(
        "dashboard.html",
        metrics=metrics,
        recent_projects=recent_projects,
        recent_telemetry=recent_telemetry, metric_links=metric_links,
        can_create_project=can_manage_operations,
    )

``


## ARCHIVO: app\projects.py

``text
import sqlite3

from flask import Blueprint, flash, redirect, render_template, request, url_for

from .db import execute, fetch_all, fetch_one
from .utils import delete_confirmation, login_required, roles_required, soft_delete_entity

bp = Blueprint("projects", __name__, url_prefix="/proyectos")


@bp.get("")
@login_required
def project_list():
    projects = fetch_all(
        """
        SELECT p.*, e.first_name || ' ' || e.last_name AS manager_name,
               (SELECT COUNT(*) FROM project_phases ph WHERE ph.project_id = p.id) AS phase_count,
               COALESCE((SELECT AVG(ph.progress_percent) FROM project_phases ph WHERE ph.project_id = p.id), 0) AS progress
        FROM projects p
        LEFT JOIN employees e ON e.id = p.project_manager_employee_id
        WHERE p.deleted_at IS NULL
        ORDER BY CASE p.status WHEN 'active' THEN 0 WHEN 'planning' THEN 1 ELSE 2 END, p.planned_end_date
        """
    )
    return render_template("projects/list.html", projects=projects)


@bp.route("/nuevo", methods=("GET", "POST"))
@login_required
@roles_required("admin", "gerencia", "coordinador_operativo", "supervisor_operaciones")
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
@roles_required("admin", "gerencia", "coordinador_operativo", "supervisor_operaciones")
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
@roles_required("admin", "gerencia", "coordinador_operativo", "supervisor_operaciones")
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
@roles_required("admin", "gerencia", "coordinador_operativo", "supervisor_operaciones")
def phase_create(project_id):
    project = fetch_one("SELECT id FROM projects WHERE id = ? AND deleted_at IS NULL", (project_id,))
    if project is None:
        return render_template("error.html", code=404, message="Proyecto no encontrado."), 404
    data = request.form
    try:
        execute(
            """
            INSERT INTO project_phases (project_id, name, sequence, planned_start, planned_end, progress_percent, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id, data.get("name", "").strip(), data.get("sequence") or 1,
                data.get("planned_start") or None, data.get("planned_end") or None,
                data.get("progress_percent") or 0, data.get("status", "pending"),
            ),
        )
        flash("Fase agregada al cronograma.", "success")
    except sqlite3.IntegrityError:
        flash("No se pudo agregar la fase. Verifica nombre, secuencia y progreso.", "danger")
    return redirect(url_for("projects.project_detail", project_id=project_id))


@bp.post("/<int:project_id>/asignaciones")
@login_required
@roles_required("admin", "gerencia", "coordinador_operativo", "supervisor_operaciones")
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
        execute(
            f"INSERT INTO project_assignments (project_id, {column}, role, assigned_from, assigned_to) VALUES (?, ?, ?, ?, ?)",
            (
                project_id, resource_id, request.form.get("role", "").strip() or None,
                request.form.get("assigned_from") or None, request.form.get("assigned_to") or None,
            ),
        )
        flash("Recurso asignado al proyecto.", "success")
    except sqlite3.IntegrityError:
        flash("No se pudo asignar el recurso. Verifica los datos.", "danger")
    return redirect(url_for("projects.project_detail", project_id=project_id))

``


## ARCHIVO: app\reference_data.py

``text
"""Catálogos iniciales del ERP. Son editables y no sustituyen validaciones legales."""
import json

CATALOGS = {
    "document_type": ("Tipo de documento", "Tipos de identificación usados en Colombia."),
    "blood_type": ("Tipo de sangre", "Grupo ABO y factor Rh."),
    "eps": ("EPS", "Entidades promotoras de salud para sugerencias de captura."),
    "arl": ("ARL", "Administradoras de riesgos laborales."),
    "pension_fund": ("Fondo de pensiones", "Fondos y administradora pública."),
    "bank": ("Banco", "Entidades financieras y billeteras usadas para pagos."),
    "account_type": ("Tipo de cuenta", "Tipos de cuenta para pagos."),
    "education_level": ("Nivel educativo", "Niveles de formación."),
    "marital_status": ("Estado civil", "Estados civiles para ficha de personal."),
    "contract_type": ("Tipo de contrato", "Modalidades contractuales de referencia."),
    "job_position": ("Cargo", "Cargos operativos y administrativos frecuentes."),
    "material_unit": ("Unidad de material", "Unidades de inventario y consumo."),
    "maintenance_type": ("Tipo de mantenimiento", "Clasificación del mantenimiento."),
    "municipality": ("Municipio", "Municipios frecuentes de la región Caribe."),
}

ITEMS = {
    "document_type": [("CC", "Cédula de ciudadanía"), ("CE", "Cédula de extranjería"), ("NIT", "NIT"), ("PP", "Pasaporte")],
    "blood_type": [(x, x) for x in ("O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-")],
    "eps": [
        ("EPS037", "NUEVA EPS"), ("EPS042", "COOSALUD EPS"), ("EPS005", "EPS SANITAS"),
        ("EPS010", "EPS SURA"), ("EPS008", "COMPENSAR EPS"), ("EPS002", "SALUD TOTAL EPS"),
        ("EPS016", "FAMISANAR EPS"), ("EPS017", "FAMISANAR EPS"), ("EPS018", "EPS SOS"), ("EPS003", "CAFESALUD EPS"),
        ("EPS013", "SALUDCOOP EPS"), ("ESS024", "ASMET SALUD"), ("ESS207", "MUTUALSER EPS"),
        ("ESS118", "EMSSANAR EPS"), ("EPSI05", "ANAS WAYUU EPSI"), ("CCF055", "CAJACOPI ATLÁNTICO EPS"),
        ("EPSI04", "ANAS WAYUU EPSI"), ("EPSI06", "PIJAOS SALUD EPSI"), ("ESS062", "ASOCIACIÓN INDÍGENA DEL CAUCA EPSI"),
        ("EPS-SAVIA", "SAVIA SALUD EPS"), ("EPS-CAPITAL", "CAPITAL SALUD EPS"), ("EPS-COMFACHOCO", "COMFACHOCÓ EPS"),
        ("EPS041", "NUEVA EPS"), ("EPS048", "MUTUAL SER"), ("ESSC07", "MUTUAL SER"), ("ESSC24", "COOSALUD EPS"), ("CCFC55", "CAJACOPI EPS"),
    ],
    "arl": [
        ("ARL-AXA", "AXA COLPATRIA SEGUROS S.A."), ("ARL-COLMENA", "COLMENA SEGUROS RIESGOS LABORALES S.A."),
        ("ARL-BOLIVAR", "COMPAÑÍA DE SEGUROS BOLÍVAR S.A."), ("ARL-COLSANITAS", "COMPAÑÍA DE SEGUROS COLSANITAS S.A."),
        ("ARL-AURORA", "COMPAÑÍA DE SEGUROS DE VIDA AURORA S.A."), ("ARL-EQUIDAD", "LA EQUIDAD SEGUROS DE VIDA"),
        ("ARL-LIBERTY", "LIBERTY SEGUROS DE VIDA S.A."), ("ARL-MAPFRE", "MAPFRE COLOMBIA VIDA SEGUROS S.A."),
        ("ARL-POSITIVA", "POSITIVA COMPAÑÍA DE SEGUROS S.A."), ("14-23", "POSITIVA COMPAÑÍA DE SEGUROS S.A."),
    ],
    "pension_fund": [("COLPENSIONES", "COLPENSIONES"), ("PROTECCION", "PROTECCIÓN"), ("PORVENIR", "PORVENIR"), ("SKANDIA", "SKANDIA"), ("COLFONDOS", "COLFONDOS"), ("230201", "PROTECCIÓN"), ("230301", "PORVENIR"), ("25-14", "COLPENSIONES")],
    "bank": [("BANCOLOMBIA", "BANCOLOMBIA"), ("BOGOTA", "BANCO DE BOGOTÁ"), ("DAVIVIENDA", "DAVIVIENDA"), ("BBVA", "BBVA COLOMBIA"), ("OCCIDENTE", "BANCO DE OCCIDENTE"), ("POPULAR", "BANCO POPULAR"), ("COLPATRIA", "SCOTIABANK COLPATRIA"), ("ITAU", "ITAÚ"), ("NEQUI", "NEQUI"), ("DAVIPLATA", "DAVIPLATA")],
    "account_type": [("SAVINGS", "Cuenta de ahorros"), ("CURRENT", "Cuenta corriente")],
    "education_level": [(x.upper().replace(" ", "_"), x) for x in ("Primaria", "Bachillerato", "Técnico", "Tecnólogo", "Profesional", "Especialización", "Maestría", "Doctorado")],
    "marital_status": [(x.upper().replace(" ", "_"), x) for x in ("Soltero/a", "Casado/a", "Unión libre", "Separado/a", "Divorciado/a", "Viudo/a")],
    "contract_type": [(x.upper().replace(" ", "_"), x) for x in ("Término indefinido", "Término fijo", "Obra o labor", "Prestación de servicios", "Aprendizaje", "Jornal")],
    "job_position": [(x.upper().replace(" ", "_"), x) for x in ("Gerente de proyecto", "Supervisor de obra", "Oficial de jardinería", "Jardinero", "Operario de mantenimiento", "Auxiliar de jardinería", "Técnico SST", "Conductor", "Maquinista", "Almacenista", "Compras", "Auxiliar administrativo")],
    "material_unit": [(x, x) for x in ("unidad", "kg", "g", "m", "m²", "m³", "L", "galón", "saco", "bulto", "rollo", "caja", "par")],
    "maintenance_type": [(x.upper(), x) for x in ("Preventivo", "Correctivo", "Inspección")],
    "municipality": [(x.upper().replace(" ", "_"), x) for x in ("Cartagena", "Barranquilla", "Santa Marta", "Turbaco", "Arjona", "Clemencia", "Santa Catalina", "Puerto Colombia", "Soledad", "Malambo")],
}


def seed_reference_data(db):
    for code, (name, description) in CATALOGS.items():
        db.execute("INSERT OR IGNORE INTO reference_catalogs(code, name, description) VALUES (?, ?, ?)", (code, name, description))
    for catalog_code, items in ITEMS.items():
        for sort_order, (code, name) in enumerate(items, start=1):
            db.execute(
                "INSERT OR IGNORE INTO reference_items(catalog_code, code, name, metadata_json, sort_order) VALUES (?, ?, ?, ?, ?)",
                (catalog_code, code, name, json.dumps({"source": "catálogo inicial editable"}, ensure_ascii=False), sort_order),
            )
            db.execute(
                "UPDATE reference_items SET name=?, metadata_json=?, sort_order=? WHERE catalog_code=? AND code=?",
                (name, json.dumps({"source": "catálogo inicial editable"}, ensure_ascii=False), sort_order, catalog_code, code),
            )
    db.execute("""
        -- 25-14 is the PILA code for Colpensiones (pension), not an ARL.
        -- The imported planillas show 14-23 as the company's ARL Positiva.
        UPDATE employees SET arl='14-23'
        WHERE arl='25-14' AND pension_fund='25-14'
    """)
    db.execute("""
        UPDATE employees SET
            eps_reference_id=(SELECT id FROM reference_items r WHERE r.catalog_code='eps' AND r.code=employees.eps),
            pension_fund_reference_id=(SELECT id FROM reference_items r WHERE r.catalog_code='pension_fund' AND r.code=employees.pension_fund),
            arl_reference_id=(SELECT id FROM reference_items r WHERE r.catalog_code='arl' AND r.code=employees.arl)
        WHERE deleted_at IS NULL
    """)

``


## ARCHIVO: app\resources.py

``text
import sqlite3

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from .db import execute, fetch_all, fetch_one
from .utils import login_required, roles_required

bp = Blueprint("resources", __name__, url_prefix="/recursos")


@bp.get("/materiales")
@login_required
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
            execute(
                """
                INSERT INTO materials (sku, name, unit, minimum_stock, current_stock, unit_cost, supplier)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data.get("sku", "").strip(), data.get("name", "").strip(), data.get("unit", "").strip(),
                    data.get("minimum_stock") or 0, data.get("current_stock") or 0,
                    data.get("unit_cost") or 0, data.get("supplier", "").strip() or None,
                ),
            )
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
    quantity = float(request.form.get("quantity") or 0)
    if movement_type not in {"in", "out", "return", "adjustment"} or quantity <= 0:
        flash("Tipo o cantidad de movimiento no válidos.", "danger")
        return redirect(url_for("resources.materials_list"))
    delta = -quantity if movement_type == "out" else quantity
    new_stock = float(material["current_stock"] or 0) + delta
    if new_stock < 0:
        flash("El movimiento dejaría el inventario en negativo.", "danger")
        return redirect(url_for("resources.materials_list"))
    execute(
        "INSERT INTO inventory_movements (material_id, project_id, movement_type, quantity, unit_cost, reference, created_by_user_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            material_id, request.form.get("project_id") or None, movement_type, quantity,
            request.form.get("unit_cost") or material["unit_cost"] or 0,
            request.form.get("reference", "").strip() or None, g.user["id"],
        ),
    )
    execute("UPDATE materials SET current_stock=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (new_stock, material_id))
    flash("Movimiento de inventario registrado.", "success")
    return redirect(url_for("resources.materials_list"))


@bp.get("/maquinaria")
@login_required
def equipment_list():
    equipment = fetch_all(
        """
        SELECT eq.*, p.code AS project_code,
               (SELECT COUNT(*) FROM equipment_maintenance em WHERE em.equipment_id = eq.id AND em.status='scheduled') AS pending_maintenance
        FROM equipment eq LEFT JOIN projects p ON p.id = eq.project_id
        WHERE eq.deleted_at IS NULL ORDER BY eq.name
        """
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
            execute(
                """
                INSERT INTO equipment (asset_code, name, equipment_type, brand, model, serial_number, status, location, project_id, next_service_date, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data.get("asset_code", "").strip(), data.get("name", "").strip(), data.get("equipment_type", "").strip() or None,
                    data.get("brand", "").strip() or None, data.get("model", "").strip() or None,
                    data.get("serial_number", "").strip() or None, data.get("status", "available"),
                    data.get("location", "").strip() or None, data.get("project_id") or None,
                    data.get("next_service_date") or None, data.get("notes", "").strip() or None,
                ),
            )
            flash("Maquinaria registrada.", "success")
            return redirect(url_for("resources.equipment_list"))
        except sqlite3.IntegrityError:
            flash("El código de activo ya existe o los datos no son válidos.", "danger")
    return render_template("resources/equipment_form.html", projects=projects)


@bp.post("/maquinaria/<int:equipment_id>/mantenimiento")
@login_required
@roles_required("admin", "gerencia", "coordinador_operativo", "supervisor_operaciones")
def maintenance_create(equipment_id):
    equipment = fetch_one("SELECT id FROM equipment WHERE id=? AND deleted_at IS NULL", (equipment_id,))
    if equipment is None:
        return render_template("error.html", code=404, message="Equipo no encontrado."), 404
    execute(
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
    )
    execute("UPDATE equipment SET next_service_date=?, status='maintenance', updated_at=CURRENT_TIMESTAMP WHERE id=?", (request.form.get("scheduled_date"), equipment_id))
    flash("Mantenimiento programado.", "success")
    return redirect(url_for("resources.equipment_list"))


@bp.get("/auditorias")
@login_required
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
        execute(
            "INSERT INTO audits (project_id, audit_type, audit_date, auditor_user_id, score, findings) VALUES (?, ?, ?, ?, ?, ?)",
            (
                request.form.get("project_id") or None, request.form.get("audit_type", "operational"),
                request.form.get("audit_date"), g.user["id"],
                request.form.get("score") or None, request.form.get("findings", "").strip() or None,
            ),
        )
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
    execute(
        "INSERT INTO action_plans (audit_id, description, responsible_employee_id, due_date, evidence_url) VALUES (?, ?, ?, ?, ?)",
        (
            audit_id, request.form.get("description", "").strip(), request.form.get("responsible_employee_id") or None,
            request.form.get("due_date") or None, request.form.get("evidence_url", "").strip() or None,
        ),
    )
    flash("Plan de acción creado.", "success")
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
        flash("Estado del plan de acción actualizado.", "success")
    return redirect(url_for("resources.audits_list"))

``


## ARCHIVO: app\sst.py

``text
import hmac
import json
import sqlite3
from datetime import datetime, timezone

from flask import Blueprint, current_app, flash, g, jsonify, redirect, render_template, request, url_for

from .db import execute, fetch_all, fetch_one
from .utils import login_required, roles_required

bp = Blueprint("sst", __name__)


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
            SELECT si.id, si.incident_type, si.severity, si.occurred_at, si.status,
                   p.code AS project_code
            FROM sst_incidents si LEFT JOIN projects p ON p.id = si.project_id
            ORDER BY si.occurred_at DESC, si.id DESC LIMIT 6
            """
        )],
    }


@bp.get("/sst")
@login_required
def dashboard():
    return render_template("sst/dashboard.html", data=dashboard_data())


@bp.get("/api/sst/dashboard")
@login_required
def dashboard_api():
    return jsonify(dashboard_data())


@bp.route("/sst/inspecciones/nueva", methods=("GET", "POST"))
@login_required
@roles_required("admin", "gerencia", "sst", "operaciones", "coordinador_operativo")
def inspection_create():
    projects = fetch_all("SELECT id, code, name FROM projects WHERE deleted_at IS NULL ORDER BY code")
    if request.method == "POST":
        try:
            compliance = float(request.form.get("compliance_percent") or 0)
            if not 0 <= compliance <= 100:
                raise ValueError
            execute(
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
            flash("Inspección SST registrada.", "success")
            return redirect(url_for("sst.dashboard"))
        except (TypeError, ValueError, sqlite3.IntegrityError):
            flash("Verifica la fecha, el porcentaje y los datos de la inspección.", "danger")
    return render_template("sst/inspection_form.html", projects=projects)


@bp.route("/sst/incidentes/nuevo", methods=("GET", "POST"))
@login_required
@roles_required("admin", "gerencia", "sst", "operaciones", "coordinador_operativo")
def incident_create():
    projects = fetch_all("SELECT id, code, name FROM projects WHERE deleted_at IS NULL ORDER BY code")
    employees = fetch_all(
        "SELECT id, first_name || ' ' || last_name AS name FROM employees WHERE status='active' AND deleted_at IS NULL ORDER BY name"
    )
    if request.method == "POST":
        try:
            occurred_at = request.form.get("occurred_at") or datetime.now(timezone.utc).isoformat(timespec="minutes")
            execute(
                """
                INSERT INTO sst_incidents
                (project_id, employee_id, incident_type, severity, occurred_at, description, reported_by_user_id, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'open')
                """,
                (
                    request.form.get("project_id") or None, request.form.get("employee_id") or None,
                    request.form.get("incident_type", "unsafe_condition"), request.form.get("severity", "medium"),
                    occurred_at, request.form.get("description", "").strip(), g.user["id"],
                ),
            )
            flash("Incidente SST registrado.", "success")
            return redirect(url_for("sst.dashboard"))
        except sqlite3.IntegrityError:
            flash("Verifica el tipo, severidad y los datos del incidente.", "danger")
    return render_template("sst/incident_form.html", projects=projects, employees=employees)


@bp.post("/sst/incidentes/<int:incident_id>/estado")
@login_required
@roles_required("admin", "gerencia", "sst", "operaciones", "coordinador_operativo")
def incident_status(incident_id):
    status = request.form.get("status", "investigating")
    if status not in {"open", "investigating", "closed"}:
        flash("Estado de incidente no válido.", "danger")
    else:
        execute("UPDATE sst_incidents SET status=? WHERE id=?", (status, incident_id))
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
    required = ("incident_type", "severity", "occurred_at", "description")
    missing = [field for field in required if not payload.get(field)]
    if missing:
        return jsonify(error="Faltan campos obligatorios", fields=missing), 422
    if payload["incident_type"] not in {"near_miss", "accident", "illness", "unsafe_condition"}:
        return jsonify(error="incident_type no válido"), 422
    if payload["severity"] not in {"low", "medium", "high", "critical"}:
        return jsonify(error="severity no válido"), 422
    try:
        incident_id = execute(
            """
            INSERT INTO sst_incidents
            (project_id, employee_id, incident_type, severity, occurred_at, description, status)
            VALUES (?, ?, ?, ?, ?, ?, 'open')
            """,
            (
                payload.get("project_id"), payload.get("employee_id"), payload["incident_type"],
                payload["severity"], payload["occurred_at"], payload["description"],
            ),
        ).lastrowid
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
    except (TypeError, ValueError):
        return jsonify(error="El cuerpo JSON no es válido"), 400
    except sqlite3.IntegrityError:
        return jsonify(error="project_id o employee_id no válidos"), 422
    return jsonify(id=event_id, status="accepted"), 201

``


## ARCHIVO: app\static\css\app.css

``text
:root {
  --app-teal: #0f766e;
  --app-teal-dark: #115e59;
  --app-ink: #172033;
  --app-muted: #64748b;
  --app-bg: #f5f7fb;
}

body { background: var(--app-bg); color: var(--app-ink); font-size: .95rem; }
.app-navbar { background: linear-gradient(115deg, var(--app-teal-dark), var(--app-teal)); box-shadow: 0 2px 12px rgba(15, 118, 110, .18); }
.navbar-brand { font-weight: 700; letter-spacing: -.02em; }
.brand-mark, .auth-logo { display: inline-flex; align-items: center; justify-content: center; background: rgba(255,255,255,.16); border-radius: 12px; width: 38px; height: 38px; }
.brand-subtitle { font-size: .62rem; opacity: .75; font-weight: 400; letter-spacing: .02em; }
.user-menu { color: #fff; border-color: rgba(255,255,255,.35); }
.page-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; flex-wrap: wrap; margin-bottom: 1.5rem; }
.eyebrow { display: block; color: var(--app-teal); font-size: .72rem; font-weight: 800; letter-spacing: .1em; text-transform: uppercase; margin-bottom: .35rem; }
.metric-card { display: flex; align-items: center; gap: .85rem; height: 100%; padding: 1rem; background: #fff; border-radius: .85rem; box-shadow: 0 2px 14px rgba(15, 23, 42, .055); }
.metric-icon { display: inline-flex; align-items: center; justify-content: center; flex: 0 0 42px; width: 42px; height: 42px; border-radius: 12px; font-size: 1.15rem; }
.metric-label { color: var(--app-muted); font-size: .72rem; font-weight: 700; }
.metric-value { font-size: 1.55rem; font-weight: 800; line-height: 1.2; }
.metric-note { color: var(--app-muted); font-size: .7rem; }
.bg-teal { background: #ccfbf1; color: #0f766e; }.bg-blue { background: #dbeafe; color: #1d4ed8; }.bg-orange { background: #ffedd5; color: #c2410c; }.bg-purple { background: #f3e8ff; color: #7e22ce; }.bg-red { background: #fee2e2; color: #b91c1c; }
.text-teal { color: var(--app-teal); }.bg-teal { background-color: var(--app-teal) !important; color: #fff; }
.status-pill, .severity { display: inline-flex; align-items: center; border-radius: 999px; font-size: .72rem; font-weight: 700; padding: .28rem .58rem; white-space: nowrap; }
.status-active, .status-completed { background: #dcfce7; color: #166534; }.status-planning, .status-pending { background: #e0f2fe; color: #075985; }.status-paused, .status-suspended, .status-in_progress { background: #fef3c7; color: #92400e; }.status-cancelled, .status-inactive, .status-blocked { background: #f1f5f9; color: #475569; }
.status-calculated { background: #dcfce7; color: #166534; }.status-closed, .status-paid { background: #e2e8f0; color: #334155; }
.severity-info { background: #e0f2fe; color: #075985; }.severity-low { background: #dcfce7; color: #166534; }.severity-medium { background: #fef3c7; color: #92400e; }.severity-high, .severity-critical { background: #fee2e2; color: #b91c1c; }
.card { border-radius: .85rem; overflow: hidden; }.card-header { padding: 1rem 1.1rem; }.table > :not(caption) > * > * { padding: .85rem 1rem; }.table thead th { color: var(--app-muted); font-size: .72rem; text-transform: uppercase; letter-spacing: .04em; white-space: nowrap; }
.form-control, .form-select { border-color: #dbe2ea; border-radius: .55rem; }.form-control:focus, .form-select:focus { border-color: var(--app-teal); box-shadow: 0 0 0 .2rem rgba(15,118,110,.12); }.btn { border-radius: .55rem; }.btn-primary { --bs-btn-bg: var(--app-teal); --bs-btn-border-color: var(--app-teal); --bs-btn-hover-bg: var(--app-teal-dark); --bs-btn-hover-border-color: var(--app-teal-dark); }
.progress { height: .45rem; background: #e2e8f0; }.timeline-item + .timeline-item { border-top: 1px solid #e2e8f0; margin-top: 1rem; padding-top: 1rem; }
.nine-box { display: grid; grid-template-columns: 30px repeat(3, minmax(0, 1fr)); grid-template-rows: repeat(3, minmax(84px, 1fr)) 26px; gap: .4rem; }
.nine-axis { color: var(--app-muted); font-size: .72rem; font-weight: 800; text-transform: uppercase; letter-spacing: .04em; display: flex; align-items: center; justify-content: center; }
.nine-axis-y { grid-column: 1; grid-row: 1 / span 3; writing-mode: vertical-rl; transform: rotate(180deg); }
.nine-axis-x { grid-column: 2 / span 3; grid-row: 4; }
.nine-cell { border-radius: .65rem; padding: .55rem; display: flex; flex-direction: column; justify-content: center; text-align: center; font-size: .7rem; line-height: 1.2; }
.nine-cell strong { font-size: .72rem; margin-top: .15rem; }
.cell-low { background: #fee2e2; color: #991b1b; }.cell-medium { background: #fef3c7; color: #92400e; }.cell-high { background: #dcfce7; color: #166534; }
.movement-qty { max-width: 90px; }
.auth-shell { min-height: calc(100vh - 170px); }.auth-card { border-radius: 1rem; }.auth-logo { width: 58px; height: 58px; border-radius: 18px; background: #ccfbf1; color: var(--app-teal); font-size: 1.45rem; margin: auto; }.empty-state { min-height: 45vh; }
.flash-stack { max-width: 760px; margin: 0 auto 1rem; }
.record-lookup { position: relative; }.lookup-results { position: absolute; z-index: 20; left: 0; right: 0; top: calc(100% + .25rem); max-height: 260px; overflow-y: auto; background: #fff; border: 1px solid #dbe2ea; border-radius: .6rem; box-shadow: 0 8px 24px rgba(15, 23, 42, .14); }.lookup-result { display: flex; flex-direction: column; width: 100%; gap: .1rem; padding: .65rem .75rem; text-align: left; border: 0; border-bottom: 1px solid #eef2f7; background: #fff; }.lookup-result:hover, .lookup-result:focus { background: #f0fdfa; }.lookup-result small { color: var(--app-muted); }.linked-context { margin-top: .75rem; padding: .7rem .8rem; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: .6rem; }

@media (max-width: 575.98px) {
  main { padding-top: 1.25rem !important; }
  .page-heading { margin-bottom: 1.15rem; }
  .page-heading .btn { width: 100%; }
  .metric-card { padding: .8rem; }
  .metric-icon { flex-basis: 36px; width: 36px; height: 36px; font-size: 1rem; }
  .metric-value { font-size: 1.3rem; }
  .metric-note { display: none; }
  .table { font-size: .86rem; }
  .table > :not(caption) > * > * { padding: .7rem .75rem; }
  .nine-box { grid-template-columns: 22px repeat(3, minmax(0, 1fr)); grid-template-rows: repeat(3, minmax(78px, 1fr)) 22px; gap: .25rem; }
  .nine-cell { padding: .3rem; font-size: .58rem; }
  .nine-cell strong { font-size: .6rem; }
}

/* Identidad visual Costa Verde: más limpia, cálida y orientada a operación. */
:root {
  --app-teal: #087f5b;
  --app-teal-dark: #07553f;
  --app-ink: #18312b;
  --app-muted: #6a7c78;
  --app-bg: #f3f8f5;
  --app-sand: #f3b562;
}
body { background: radial-gradient(circle at 100% 0%, #e4f4ec 0, transparent 32rem), var(--app-bg); }
.app-navbar { background: linear-gradient(118deg, #064e3b 0%, #087f5b 58%, #159a70 100%); box-shadow: 0 8px 28px rgba(5, 83, 62, .22); }
.navbar-brand { letter-spacing: -.035em; }
.brand-mark { background: rgba(255,255,255,.2); box-shadow: inset 0 0 0 1px rgba(255,255,255,.18); }
.nav-link { border-radius: .55rem; transition: background .2s ease, transform .2s ease; }
.nav-link:hover { background: rgba(255,255,255,.12); transform: translateY(-1px); }
.page-heading { padding: 1.15rem 1.25rem; border: 1px solid rgba(8,127,91,.1); border-radius: 1rem; background: linear-gradient(120deg, rgba(255,255,255,.92), rgba(239,250,244,.9)); box-shadow: 0 8px 24px rgba(33, 73, 60, .05); }
.page-heading h1 { color: #123b2e; letter-spacing: -.04em; font-weight: 800; }
.eyebrow { color: var(--app-teal); }
.metric-card, .card { border: 1px solid rgba(21, 91, 68, .08) !important; box-shadow: 0 8px 24px rgba(30, 75, 58, .07) !important; }
.metric-card { border-radius: 1rem; transition: transform .2s ease, box-shadow .2s ease; }
.metric-card:hover { transform: translateY(-2px); box-shadow: 0 12px 30px rgba(30, 75, 58, .12) !important; }
.metric-icon { border-radius: 14px; }
.card-header { background: linear-gradient(120deg, #fff, #f8fcf9) !important; border-bottom-color: #e1eee7; }
.table thead th { color: #55736a; }
.btn-primary { box-shadow: 0 5px 12px rgba(8,127,91,.18); }
.btn-primary:hover { transform: translateY(-1px); box-shadow: 0 7px 15px rgba(8,127,91,.24); }
.form-control, .form-select { background-color: rgba(255,255,255,.9); }
.status-active, .status-completed { background: #d7f4e3; color: #146c43; }
.bg-teal { background: #087f5b !important; }
.text-teal { color: #087f5b !important; }
.auth-card { box-shadow: 0 18px 45px rgba(30, 75, 58, .13) !important; }
.lookup-results { border-color: #b9dfcc; }

/* Shell premium: layout inspirado en paneles operativos modernos. */
.erp-body { background: #f4f7f5; }
.erp-shell { min-height: 100vh; display: flex; }
.app-sidebar { position: fixed; z-index: 1040; inset: 0 auto 0 0; width: 274px; display: flex; flex-direction: column; background: #082f24; color: #c9dfd5; box-shadow: 10px 0 32px rgba(3, 35, 26, .12); }
.sidebar-brand { min-height: 84px; padding: 1.25rem 1.35rem; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid rgba(255,255,255,.08); }
.brand-link { display: inline-flex; align-items: center; gap: .7rem; color: inherit; text-decoration: none; }
.brand-link strong { display: block; color: #fff; font-size: 1rem; line-height: 1.05; letter-spacing: -.03em; }
.brand-link small { display: block; color: #91b7a8; font-size: .68rem; margin-top: .25rem; }
.app-sidebar .brand-mark, .public-header .brand-mark { width: 39px; height: 39px; flex: 0 0 39px; border-radius: 12px; display: inline-flex; align-items: center; justify-content: center; color: #ddf7e8; background: linear-gradient(145deg, #22a16f, #0b684b); box-shadow: 0 6px 14px rgba(0,0,0,.18); }
.brand-image { overflow: hidden; padding: 0; background: #fff !important; }.brand-image img { width: 100%; height: 100%; object-fit: cover; display: block; }
.sidebar-caption { margin: 1.35rem 1.25rem .55rem; color: #6c9a87; font-size: .66rem; font-weight: 800; letter-spacing: .13em; text-transform: uppercase; }
.sidebar-nav { overflow-y: auto; padding: 0 .8rem 1rem; }
.sidebar-section { margin: 1.25rem .65rem .4rem; color: #628d7c; font-size: .62rem; font-weight: 800; text-transform: uppercase; letter-spacing: .11em; }
.sidebar-link { display: flex; align-items: center; gap: .75rem; margin: .14rem 0; padding: .7rem .72rem; border-radius: .7rem; color: #b2d2c3; text-decoration: none; font-size: .84rem; font-weight: 600; transition: background .2s ease, color .2s ease, transform .2s ease; }
.sidebar-link i { width: 1.15rem; color: #79b799; font-size: 1rem; text-align: center; }
.sidebar-link:hover, .sidebar-link:focus { color: #fff; background: rgba(111, 202, 158, .13); transform: translateX(2px); }
.sidebar-link:hover i { color: #c4f2d7; }
.sidebar-footer { margin-top: auto; padding: 1rem; border-top: 1px solid rgba(255,255,255,.08); }
.secure-badge { display: flex; align-items: center; gap: .65rem; padding: .7rem .75rem; border: 1px solid rgba(160,231,192,.16); border-radius: .75rem; background: rgba(118,206,159,.08); }
.secure-badge i { color: #84d8a6; font-size: 1.1rem; }.secure-badge strong, .secure-badge small { display: block; }.secure-badge strong { color: #d9f5e5; font-size: .7rem; }.secure-badge small { color: #85ad9b; font-size: .63rem; margin-top: .12rem; }
.sidebar-close { border: 0; background: transparent; color: #9bc7b4; font-size: 1.15rem; }
.erp-main { min-width: 0; width: calc(100% - 274px); margin-left: 274px; }
.app-topbar { height: 84px; padding: 0 2.3rem; display: flex; align-items: center; justify-content: space-between; background: rgba(255,255,255,.82); border-bottom: 1px solid #e1ebe5; backdrop-filter: blur(14px); }
.topbar-context { display: flex; align-items: center; gap: .75rem; }.topbar-logo { width: 40px; height: 40px; object-fit: cover; border-radius: 11px; box-shadow: 0 4px 12px rgba(8,127,91,.16); }.topbar-logo-large { width: 52px; height: 52px; border-radius: 14px; }.topbar-copy { display: flex; flex-direction: column; }.topbar-kicker { color: #7a9187; font-size: .69rem; font-weight: 700; letter-spacing: .07em; text-transform: uppercase; }.topbar-title { color: #17392d; font-size: 1.05rem; font-weight: 800; letter-spacing: -.025em; }
.topbar-actions { display: flex; align-items: center; gap: .8rem; }.quick-action { display: inline-flex; align-items: center; gap: .45rem; padding: .5rem .7rem; border: 1px solid #dce9e1; border-radius: .65rem; color: #3d6b57; background: #fff; text-decoration: none; font-size: .78rem; font-weight: 700; }.quick-action:hover { background: #eff9f3; color: #086b4d; }
.profile-chip { display: flex; align-items: center; gap: .55rem; padding: .25rem .45rem .25rem .25rem; border: 0; background: transparent; color: #234739; }.profile-chip::after { margin-left: .15rem; }.profile-chip strong { display: block; max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: .75rem; }.profile-chip small { color: #7a9187; font-size: .62rem; }.profile-avatar { width: 35px; height: 35px; display: inline-flex; align-items: center; justify-content: center; border-radius: 11px; color: #fff; background: linear-gradient(145deg, #1caa78, #07563f); font-weight: 800; box-shadow: 0 4px 10px rgba(8,127,91,.18); }
.workspace-container { max-width: 1680px; margin: 0 auto; padding: 2rem 2.3rem 1rem; }.workspace-footer { padding: .7rem 2.3rem 1.4rem; color: #92a69d; font-size: .68rem; }.workspace-footer span { padding: 0 .3rem; color: #bdd0c5; }.sidebar-toggle { border: 1px solid #dbe8e0; border-radius: .6rem; background: #fff; color: #287056; font-size: 1.25rem; }
.sidebar-backdrop { display: none; }
.public-body { min-height: 100vh; background: radial-gradient(circle at 100% 0, #ddf4e7 0, transparent 34rem), linear-gradient(145deg, #f4faf6, #edf5f1); }.public-header { height: 84px; padding: 0 clamp(1.25rem, 5vw, 5rem); display: flex; align-items: center; justify-content: space-between; }.public-header .brand-link strong { color: #174b37; }.public-header .brand-link small { color: #719282; }.public-status { color: #54806b; font-size: .72rem; font-weight: 700; }.public-status i { color: #18a56e; font-size: .45rem; vertical-align: middle; margin-right: .35rem; }.public-container { min-height: calc(100vh - 84px); padding: 1rem clamp(1rem, 5vw, 5rem) 3rem; display: flex; flex-direction: column; justify-content: center; }
.auth-shell { position: relative; width: min(1100px, 100%); min-height: 610px; margin: auto; display: grid !important; grid-template-columns: 1.05fr .95fr; align-items: stretch !important; border-radius: 1.6rem; overflow: hidden; background: #fff; box-shadow: 0 22px 70px rgba(30, 77, 56, .14); }.auth-shell::before { content: 'Jardines de la Costa'; display: flex; flex-direction: column; justify-content: flex-end; padding: 3rem; color: #eafff1; font-size: 2.5rem; font-weight: 800; letter-spacing: -.06em; background: linear-gradient(145deg, rgba(5,60,42,.86), rgba(9,129,91,.82)), radial-gradient(circle at 35% 30%, #53c287, #073b2a 65%); }.auth-shell::after { content: 'Operación, personas y proyectos conectados en un solo lugar.'; position: absolute; left: 0; bottom: 3rem; width: 52.5%; padding: 0 3rem; color: #bce8cb; font-size: .95rem; pointer-events: none; }
.auth-shell > div { width: auto !important; max-width: none !important; display: flex; align-items: center; }.auth-card { width: 100%; border-radius: 0 !important; box-shadow: none !important; }.auth-logo { overflow: hidden; padding: 0; background: #e5f7ed; color: #087f5b; }.auth-logo img { width: 100%; height: 100%; object-fit: cover; display: block; }

@media (max-width: 991.98px) {
  .app-sidebar { transform: translateX(-100%); transition: transform .25s ease; }.sidebar-open .app-sidebar { transform: translateX(0); }.sidebar-open .sidebar-backdrop { display: block; position: fixed; z-index: 1030; inset: 0; background: rgba(2, 31, 22, .5); }.erp-main { width: 100%; margin-left: 0; }.app-topbar { padding: 0 1.25rem; gap: 1rem; }.workspace-container { padding: 1.5rem 1.25rem 1rem; }.workspace-footer { padding-left: 1.25rem; padding-right: 1.25rem; }.auth-shell { width: min(620px, 100%); grid-template-columns: 1fr; min-height: auto; }.auth-shell::before, .auth-shell::after { display: none; }.auth-shell > div { display: block; }.auth-card { border-radius: 1.6rem !important; }.auth-shell .card-body { padding: 2.4rem 1.5rem !important; }
}
@media (max-width: 575.98px) { .app-topbar { height: 70px; }.topbar-kicker { font-size: .57rem; }.topbar-title { font-size: .9rem; }.profile-avatar { width: 32px; height: 32px; }.workspace-container { padding: 1.1rem .85rem .75rem; }.page-heading { padding: 1rem; }.public-header { height: 72px; padding: 0 1rem; }.public-status { display: none; }.public-container { min-height: calc(100vh - 72px); padding: .75rem; } }
.profile-photo { width: 58px; height: 58px; border-radius: 16px; overflow: hidden; display: inline-flex; align-items: center; justify-content: center; background: #d7f3e7; color: #087f5b; font-weight: 800; font-size: 1.15rem; }
.profile-photo-lg { width: 76px; height: 76px; border-radius: 20px; font-size: 1.5rem; }
.profile-photo img { width: 100%; height: 100%; object-fit: cover; }

``


## ARCHIVO: app\static\js\lookup.js

``text
(function () {
  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;").replaceAll("'", "&#039;");

  function itemMeta(item) {
    return [item.code, item.position, item.location, item.client_name, item.status]
      .filter(Boolean).join(" · ");
  }

  function renderContext(target, payload) {
    if (!target || !payload || !payload.record) return;
    const record = payload.record;
    const blocks = [];
    if (record.client_name || record.location || record.manager_name) {
      blocks.push(`<div><strong>${escapeHtml(record.client_name || "Sin cliente")}</strong> · ${escapeHtml(record.location || "Sin ubicación")}<br><span class="text-muted">Responsable: ${escapeHtml(record.manager_name || "Sin asignar")}</span></div>`);
    } else if (record.position || record.email || record.phone) {
      blocks.push(`<div><strong>${escapeHtml(record.position || "Sin cargo")}</strong><br><span class="text-muted">${escapeHtml(record.email || "Sin correo")} · ${escapeHtml(record.phone || "Sin teléfono")}</span></div>`);
    }
    if (payload.phases?.length) blocks.push(`<div><span class="fw-semibold">Fases:</span> ${payload.phases.map((x) => escapeHtml(x.name) + " (" + Number(x.progress_percent || 0).toFixed(0) + "%)").join(" · ")}</div>`);
    if (payload.resources?.length) blocks.push(`<div><span class="fw-semibold">Recursos:</span> ${payload.resources.map((x) => escapeHtml(x.name)).join(" · ")}</div>`);
    if (payload.projects?.length) blocks.push(`<div><span class="fw-semibold">Proyectos:</span> ${payload.projects.map((x) => escapeHtml(x.code + " · " + x.name)).join(" · ")}</div>`);
    if (payload.incidents?.length) blocks.push(`<div><span class="fw-semibold">Incidentes relacionados:</span> ${payload.incidents.length}</div>`);
    target.innerHTML = blocks.length ? `<div class="linked-context small">${blocks.join("<hr class=\"my-2\">")}</div>` : "";
    target.hidden = !blocks.length;
  }

  function initLookup(control) {
    const input = control.querySelector("[data-lookup-input]");
    const hidden = control.querySelector("input[type=hidden]");
    const results = control.querySelector(".lookup-results");
    if (!input || !hidden || !results) return;
    let timer;
    let requestId = 0;
    const contextTarget = document.querySelector(control.dataset.contextTarget || "");

    const loadContext = (item) => {
      const template = control.dataset.contextUrl;
      if (!template || !contextTarget || !item?.id) return;
      const url = template.replace(/\/0\/context$/, `/${item.id}/context`);
      fetch(url, {headers: {"Accept": "application/json"}})
        .then((response) => response.ok ? response.json() : null)
        .then((payload) => renderContext(contextTarget, payload))
        .catch(() => {});
    };

    const search = () => {
      const term = input.value.trim();
      if (term.length < 1) { results.innerHTML = ""; results.hidden = true; return; }
      const current = ++requestId;
      fetch(`${control.dataset.lookupUrl}?q=${encodeURIComponent(term)}`, {headers: {"Accept": "application/json"}})
        .then((response) => response.ok ? response.json() : {items: []})
        .then((payload) => {
          if (current !== requestId) return;
          results.innerHTML = (payload.items || []).map((item) => `<button type="button" class="lookup-result" data-id="${escapeHtml(item.id)}"><span>${escapeHtml(item.label)}</span><small>${escapeHtml(itemMeta(item))}</small></button>`).join("");
          results.hidden = !(payload.items || []).length;
          results.querySelectorAll("[data-id]").forEach((button, index) => {
            button.addEventListener("click", () => {
              const item = payload.items[index];
              hidden.value = item.id;
              input.value = item.label;
              results.innerHTML = "";
              results.hidden = true;
              input.dispatchEvent(new CustomEvent("record:selected", {detail: item}));
              loadContext(item);
            });
          });
        }).catch(() => { results.innerHTML = ""; results.hidden = true; });
    };
    input.addEventListener("input", () => { hidden.value = ""; clearTimeout(timer); timer = setTimeout(search, 180); });
    input.addEventListener("focus", search);
    document.addEventListener("click", (event) => { if (!control.contains(event.target)) results.hidden = true; });
  }

  function initSelectFilters() {
    document.querySelectorAll("select").forEach((select) => {
      if (select.dataset.noFilter !== undefined || select.options.length < 8 || select.previousElementSibling?.matches("[data-select-filter]")) return;
      const input = document.createElement("input");
      input.className = "form-control form-control-sm mb-2";
      input.placeholder = "Buscar en la lista";
      input.dataset.selectFilter = `#${select.id || ""}`;
      if (!select.id) {
        select.id = `lookup-select-${Math.random().toString(36).slice(2)}`;
        input.dataset.selectFilter = `#${select.id}`;
      }
      select.parentNode.insertBefore(input, select);
    });
    document.querySelectorAll("[data-select-filter]").forEach((input) => {
      const select = document.querySelector(input.dataset.selectFilter);
      if (!select) return;
      input.addEventListener("input", () => {
        const term = input.value.trim().toLowerCase();
        select.querySelectorAll("option").forEach((option) => {
          option.hidden = Boolean(term) && !option.textContent.toLowerCase().includes(term);
        });
      });
    });
  }

  function initReferenceInputs() {
    document.querySelectorAll("[data-reference-catalog]").forEach((input) => {
      const catalog = input.dataset.referenceCatalog;
      const listId = `reference-list-${catalog}-${Math.random().toString(36).slice(2)}`;
      const datalist = document.createElement("datalist");
      datalist.id = listId;
      input.setAttribute("list", listId);
      input.parentNode.appendChild(datalist);
      let timer;
      const load = () => {
        clearTimeout(timer);
        timer = setTimeout(() => fetch(`/api/lookups/references/${encodeURIComponent(catalog)}?q=${encodeURIComponent(input.value.trim())}`)
          .then((response) => response.ok ? response.json() : {items: []})
          .then((payload) => {
            datalist.innerHTML = (payload.items || []).map((item) => `<option value="${escapeHtml(item.name)}" label="${escapeHtml(item.code)}"></option>`).join("");
          }).catch(() => {}), 120);
      };
      input.addEventListener("focus", load);
      input.addEventListener("input", load);
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".record-lookup").forEach(initLookup);
    initSelectFilters();
    initReferenceInputs();
  });
})();

``


## ARCHIVO: app\templates\admin\password_reset.html

``text
{% extends 'base.html' %}
{% block title %}Restablecer contraseña{% endblock %}
{% block content %}
<div class="page-heading"><div><span class="eyebrow">Administración</span><h1 class="h2 mb-1">Restablecer contraseña</h1><p class="text-muted mb-0">{{ user.full_name }} · Usuario: {{ user.username or '—' }}</p></div><a class="btn btn-outline-secondary" href="{{ url_for('admin.users_list') }}">Volver a usuarios</a></div>
<div class="row justify-content-center"><div class="col-12 col-lg-6"><div class="card border-0 shadow-sm"><div class="card-body p-3 p-md-4"><div class="alert alert-warning small"><i class="bi bi-shield-lock me-1"></i>Por seguridad, las contraseñas actuales nunca se pueden consultar. El administrador puede establecer una nueva.</div><form method="post"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><label class="form-label" for="new_password">Nueva contraseña</label><input id="new_password" class="form-control" type="password" name="new_password" minlength="10" required autofocus><div class="form-text">Mínimo 10 caracteres.</div><button class="btn btn-warning mt-4" type="submit">Confirmar cambio de contraseña</button></form></div></div></div></div>
{% endblock %}

``


## ARCHIVO: app\templates\admin\user_form.html

``text
{% extends 'base.html' %}
{% block title %}Nuevo usuario · Administración{% endblock %}
{% block content %}
<div class="page-heading"><div><span class="eyebrow">Administración</span><h1 class="h2 mb-0">Nuevo usuario</h1></div><a class="btn btn-outline-secondary" href="{{ url_for('admin.users_list') }}">Volver</a></div>
<div class="row justify-content-center"><div class="col-12 col-lg-7"><div class="card border-0 shadow-sm"><div class="card-body p-3 p-md-4"><form method="post"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><div class="mb-3"><label class="form-label">Colaborador</label><select class="form-select" name="employee_id" id="employee-select"><option value="">Cuenta independiente / administrador</option>{% for employee in employees %}<option value="{{ employee.id }}" data-username="{{ employee.identification_number }}" data-name="{{ employee.name }}">{{ employee.name }} · {{ employee.identification_number }}</option>{% endfor %}</select><div class="form-text">Al elegir un colaborador, el usuario de acceso será automáticamente su número de documento.</div></div><div class="mb-3"><label class="form-label">Usuario de acceso *</label><input class="form-control" name="username" id="username" required><div class="form-text">Para colaboradores: número de documento. Para una cuenta administrativa: un identificador como <code>admin2</code>.</div></div><div class="mb-3"><label class="form-label">Nombre completo *</label><input class="form-control" name="full_name" id="full-name" required></div><div class="mb-3"><label class="form-label">Correo (opcional)</label><input class="form-control" type="email" name="email"><div class="form-text">No es necesario que el colaborador tenga correo electrónico.</div></div><div class="mb-4"><label class="form-label">Contraseña temporal *</label><input class="form-control" type="password" name="password" minlength="12" required><div class="form-text">Mínimo 12 caracteres. El usuario podrá cambiarla desde su cuenta.</div></div><fieldset class="mb-4"><legend class="h6">Rol principal *</legend><div class="row g-2">{% for role in roles %}<div class="col-12 col-sm-6"><label class="border rounded-3 p-2 d-block"><input type="radio" name="role_ids" value="{{ role.id }}" class="me-2" required> <strong>{{ role.name|replace('_',' ')|title }}</strong><span class="d-block small text-muted ms-4">{{ role.description }}</span></label></div>{% endfor %}</div></fieldset><button class="btn btn-primary" type="submit">Crear usuario</button></form></div></div></div></div>
{% endblock %}
{% block scripts %}<script>const employeeSelect=document.getElementById('employee-select');const usernameInput=document.getElementById('username');const nameInput=document.getElementById('full-name');employeeSelect.addEventListener('change',()=>{const option=employeeSelect.selectedOptions[0];if(option.value){usernameInput.value=option.dataset.username||'';nameInput.value=option.dataset.name||'';usernameInput.readOnly=true;nameInput.readOnly=true;}else{usernameInput.readOnly=false;nameInput.readOnly=false;}});</script>{% endblock %}

``


## ARCHIVO: app\templates\admin\users.html

``text
{% extends 'base.html' %}
{% block title %}Usuarios y roles{% endblock %}
{% block content %}
<div class="page-heading"><div><span class="eyebrow">Administración</span><h1 class="h2 mb-1">Usuarios y roles</h1><p class="text-muted mb-0">Administra roles, accesos y credenciales.</p></div><a class="btn btn-primary" href="{{ url_for('admin.user_create') }}">Nuevo usuario</a></div>
<div class="card border-0 shadow-sm mb-3"><div class="card-body"><div class="row g-2"><div class="col-12 col-lg-6"><label class="form-label small mb-1">Buscar</label><input id="user-search" class="form-control" placeholder="Nombre, documento o usuario"></div><div class="col-6 col-lg-3"><label class="form-label small mb-1">Rol</label><select id="role-filter" class="form-select"><option value="">Todos los roles</option>{% for role in roles %}<option value="{{ role.name }}">{{ role.name|replace('_',' ')|title }}</option>{% endfor %}</select></div><div class="col-6 col-lg-3"><label class="form-label small mb-1">Estado</label><select id="status-filter" class="form-select"><option value="">Todos</option><option value="active">Activos</option><option value="inactive">Inactivos</option></select></div></div></div></div>
<div class="card border-0 shadow-sm"><div class="table-responsive"><table class="table align-middle mb-0"><thead><tr><th>Perfil</th><th>Usuario</th><th>Rol asignado</th><th>Estado</th><th class="text-end">Acciones</th></tr></thead><tbody id="users-body">{% for user in users %}<tr data-search="{{ (user.full_name ~ ' ' ~ (user.username or '') ~ ' ' ~ (user.email or ''))|lower }}" data-role="{{ user.role_names.split(', ')[0] }}" data-status="{{ 'active' if user.is_active else 'inactive' }}"><td><div class="fw-semibold">{{ user.full_name }}</div>{% if user.email and not user.email.endswith('@jdc.local') %}<div class="small text-muted">{{ user.email }}</div>{% endif %}</td><td><code>{{ user.username or user.email }}</code></td><td><form method="post" action="{{ url_for('admin.user_roles_update', user_id=user.id) }}" class="d-flex gap-2 align-items-center"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><select class="form-select form-select-sm user-role-select" name="role_ids" required>{% for role in roles %}<option value="{{ role.id }}" {% if role.name == user.role_names.split(', ')[0] %}selected{% endif %}>{{ role.name|replace('_',' ')|title }}</option>{% endfor %}</select><button class="btn btn-sm btn-outline-primary">Guardar</button></form></td><td><span class="status-pill {% if user.is_active %}status-active{% else %}status-inactive{% endif %}">{{ 'Activo' if user.is_active else 'Inactivo' }}</span></td><td class="text-end"><div class="d-flex justify-content-end gap-2 flex-wrap"><a class="btn btn-sm btn-outline-warning" href="{{ url_for('admin.user_password_reset', user_id=user.id) }}">Restablecer contraseña</a>{% if user.id != g.user.id and user.is_active %}<form method="post" action="{{ url_for('admin.user_delete', user_id=user.id) }}" onsubmit="return confirm('¿Eliminar este perfil de los accesos? El historial se conservará.');"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><button class="btn btn-sm btn-outline-danger">Eliminar</button></form>{% endif %}</div></td></tr>{% else %}<tr><td colspan="5" class="text-center text-muted py-5">No hay usuarios registrados.</td></tr>{% endfor %}</tbody></table></div></div>
<script>function filterUsers(){const q=document.getElementById('user-search').value.toLowerCase().trim(),role=document.getElementById('role-filter').value,status=document.getElementById('status-filter').value;document.querySelectorAll('#users-body tr[data-search]').forEach(row=>{row.hidden=!!((q&&!row.dataset.search.includes(q))||(role&&row.dataset.role!==role)||(status&&row.dataset.status!==status));});}['user-search','role-filter','status-filter'].forEach(id=>document.getElementById(id).addEventListener('input',filterUsers));</script><style>.user-role-select{min-width:220px}</style>
{% endblock %}

``


## ARCHIVO: app\templates\auth\change_password.html

``text
{% extends 'base.html' %}
{% block title %}Cambiar contraseña{% endblock %}
{% block content %}
<div class="row justify-content-center"><div class="col-12 col-md-8 col-lg-5">
  <div class="page-heading"><div><span class="eyebrow">Mi cuenta</span><h1 class="h3 mb-0">Cambiar contraseña</h1></div></div>
  <div class="card border-0 shadow-sm"><div class="card-body p-4">
    <form method="post">
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
      <div class="mb-3"><label class="form-label" for="current_password">Contraseña actual</label><input class="form-control" id="current_password" name="current_password" type="password" required></div>
      <div class="mb-3"><label class="form-label" for="new_password">Nueva contraseña</label><input class="form-control" id="new_password" name="new_password" type="password" minlength="10" required><div class="form-text">Usa al menos 10 caracteres.</div></div>
      <div class="mb-4"><label class="form-label" for="confirmation">Confirmar nueva contraseña</label><input class="form-control" id="confirmation" name="confirmation" type="password" required></div>
      <div class="d-flex flex-column flex-sm-row gap-2"><button class="btn btn-primary" type="submit">Actualizar contraseña</button><a class="btn btn-outline-secondary" href="{{ url_for('main.dashboard') }}">Cancelar</a></div>
    </form>
  </div></div>
</div></div>
{% endblock %}

``


## ARCHIVO: app\templates\auth\login.html

``text
{% extends 'base.html' %}
{% block title %}Iniciar sesión · Jardines de la Costa{% endblock %}
{% block content %}
<div class="auth-shell row justify-content-center align-items-center g-0">
  <div class="col-12 col-sm-10 col-md-7 col-lg-5 col-xl-4">
    <div class="card auth-card border-0 shadow-lg">
      <div class="card-body p-4 p-sm-5">
        <div class="text-center mb-4">
          <div class="auth-logo"><img src="{{ url_for('static', filename='img/jdc-logo.ico') }}" alt="Jardines de la Costa"></div>
          <h1 class="h4 mt-3 mb-1">Bienvenido</h1>
          <p class="text-muted mb-0">Ingresa al ERP de Jardines de la Costa</p>
        </div>
        <form method="post" novalidate>
          <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
          <input type="hidden" name="next" value="{{ request.args.get('next', '') }}">
          <div class="mb-3"><label class="form-label" for="email">Usuario o número de documento</label><input class="form-control form-control-lg" type="text" id="email" name="email" autocomplete="username" required autofocus></div>
          <div class="mb-4"><label class="form-label" for="password">Contraseña</label><input class="form-control form-control-lg" type="password" id="password" name="password" autocomplete="current-password" required></div>
          <button class="btn btn-primary w-100 btn-lg" type="submit">Iniciar sesión</button>
        </form>
        <p class="text-center text-muted small mt-4 mb-0">Acceso protegido y trazable</p>
      </div>
    </div>
  </div>
</div>
{% endblock %}

``


## ARCHIVO: app\templates\base.html

``text
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#073b2a">
  <title>{% block title %}Jardines de la Costa ERP{% endblock %}</title>
  <link rel="icon" type="image/x-icon" href="{{ url_for('static', filename='img/jdc-logo.ico') }}">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css" rel="stylesheet">
  <link href="{{ url_for('static', filename='css/app.css') }}" rel="stylesheet">
</head>
<body class="{% if g.user %}erp-body{% else %}public-body{% endif %}">
{% if g.user %}
<div class="erp-shell">
  <aside class="app-sidebar" id="appSidebar">
    <div class="sidebar-brand">
      <a href="{{ url_for('main.dashboard') }}" class="brand-link">
        <span class="brand-mark brand-image"><img src="{{ url_for('static', filename='img/jdc-logo.ico') }}" alt="Jardines de la Costa"></span>
        <span><strong>Jardines</strong><small>de la Costa · ERP</small></span>
      </a>
      <button class="sidebar-close d-lg-none" type="button" data-sidebar-toggle><i class="bi bi-x-lg"></i></button>
    </div>
    <div class="sidebar-caption">Centro de control</div>
    <nav class="sidebar-nav">
      <a class="sidebar-link" href="{{ url_for('main.dashboard') }}"><i class="bi bi-grid-1x2-fill"></i><span>Inicio</span></a>
      <div class="sidebar-section">Mi operación</div>
      <a class="sidebar-link" href="{{ url_for('auth.change_password') }}"><i class="bi bi-key-fill"></i><span>Cambiar contraseña</span></a>
      <a class="sidebar-link" href="{{ url_for('employees.my_profile') }}"><i class="bi bi-person-circle"></i><span>Mi perfil</span></a>
      {% if has_role('operaciones','supervisor_operaciones','coordinador_operativo','conductor') %}
      <div class="sidebar-section">Operación</div>
      <a class="sidebar-link" href="{{ url_for('projects.project_list') }}"><i class="bi bi-kanban-fill"></i><span>Proyectos y obras</span></a>
      <a class="sidebar-link" href="{{ url_for('employees.crew_list') }}"><i class="bi bi-people-fill"></i><span>Cuadrillas</span></a>
      <a class="sidebar-link" href="{{ url_for('resources.materials_list') }}"><i class="bi bi-box-seam-fill"></i><span>Abastecimiento</span></a>
      <a class="sidebar-link" href="{{ url_for('resources.equipment_list') }}"><i class="bi bi-truck-front-fill"></i><span>Maquinaria y equipos</span></a>
      {% endif %}
      {% if is_admin or has_role('rrhh','asistente_administrativa','gerencia','coordinador_operativo','supervisor_operaciones') %}
      <div class="sidebar-section">Personas</div>
      <a class="sidebar-link" href="{{ url_for('employees.employee_list') }}"><i class="bi bi-person-vcard-fill"></i><span>Recursos humanos</span></a>
      {% if has_role('rrhh','asistente_administrativa','gerencia','coordinador_operativo') %}<a class="sidebar-link" href="{{ url_for('hr.payroll_list') }}"><i class="bi bi-cash-coin"></i><span>Nómina</span></a>{% endif %}
      <a class="sidebar-link" href="{{ url_for('hr.evaluation_list') }}"><i class="bi bi-bar-chart-line-fill"></i><span>Desempeño 9-Box</span></a>
      {% endif %}
      {% if has_role('sst','supervisor_sst','coordinador_operativo') %}
      <div class="sidebar-section">Control y cumplimiento</div>
      <a class="sidebar-link" href="{{ url_for('sst.dashboard') }}"><i class="bi bi-shield-check"></i><span>SST / HSE</span></a>
      {% endif %}
      {% if has_role('operaciones','supervisor_operaciones','coordinador_operativo','sst','supervisor_sst') %}<a class="sidebar-link" href="{{ url_for('resources.audits_list') }}"><i class="bi bi-clipboard2-check-fill"></i><span>Calidad y auditorías</span></a>{% endif %}
      {% if is_admin %}<div class="sidebar-section">Administración</div><a class="sidebar-link" href="{{ url_for('admin.users_list') }}"><i class="bi bi-person-gear"></i><span>Usuarios y permisos</span></a>{% endif %}
    </nav>
    <div class="sidebar-footer"><div class="secure-badge"><i class="bi bi-shield-lock-fill"></i><span><strong>Entorno protegido</strong><small>Actividad trazable</small></span></div></div>
  </aside>
  <div class="sidebar-backdrop" data-sidebar-toggle></div>
  <div class="erp-main">
    <header class="app-topbar">
      <button class="sidebar-toggle d-lg-none" type="button" data-sidebar-toggle><i class="bi bi-list"></i></button>
      <div class="topbar-context"><img class="topbar-logo topbar-logo-large" src="{{ url_for('static', filename='img/jdc-logo.ico') }}" alt="Jardines de la Costa"><span class="topbar-title">Centro de operaciones</span></div>
      <div class="topbar-actions"><a class="quick-action" href="{{ url_for('api.kpi_pdf') }}"><i class="bi bi-file-earmark-arrow-down"></i><span class="d-none d-md-inline">Reporte</span></a><div class="dropdown"><button class="profile-chip dropdown-toggle" data-bs-toggle="dropdown"><span class="profile-avatar">{{ g.user.full_name[:1]|upper }}</span><span class="d-none d-sm-flex flex-column text-start"><strong>{{ g.user.full_name }}</strong><small>{{ 'Administrador' if is_admin else 'Usuario del sistema' }}</small></span></button><ul class="dropdown-menu dropdown-menu-end shadow-lg"><li><a class="dropdown-item" href="{{ url_for('employees.my_profile') }}">Mi perfil</a></li>{% if is_admin %}<li><a class="dropdown-item" href="{{ url_for('admin.users_list') }}">Usuarios y permisos</a></li><li><hr class="dropdown-divider"></li>{% endif %}<li><a class="dropdown-item" href="{{ url_for('auth.change_password') }}">Cambiar contraseña</a></li><li><form method="post" action="{{ url_for('auth.logout') }}" class="px-3"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><button class="dropdown-item px-0">Cerrar sesión</button></form></li></ul></div></div>
    </header>
    <main class="workspace-container">
{% else %}
  <header class="public-header"><a href="{{ url_for('main.index') }}" class="brand-link"><span class="brand-mark brand-image"><img src="{{ url_for('static', filename='img/jdc-logo.ico') }}" alt="Jardines de la Costa"></span><span><strong>Jardines</strong><small>de la Costa · ERP</small></span></a><span class="public-status"><i class="bi bi-circle-fill"></i> Plataforma segura</span></header><main class="public-container">
{% endif %}
{% with messages = get_flashed_messages(with_categories=true) %}{% if messages %}<div class="flash-stack" aria-live="polite">{% for category,message in messages %}<div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">{{ message }}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>{% endfor %}</div>{% endif %}{% endwith %}
{% block content %}{% endblock %}
{% if g.user %}</main><footer class="workspace-footer">Jardines de la Costa S.A.S. · Sistema de Gestión Integral</footer></div></div>{% else %}</main>{% endif %}
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
<script src="{{ url_for('static', filename='js/lookup.js') }}"></script>
<script>document.querySelectorAll('[data-sidebar-toggle]').forEach(c=>c.addEventListener('click',()=>document.body.classList.toggle('sidebar-open')));</script>
{% block scripts %}{% endblock %}
</body>
</html>

``


## ARCHIVO: app\templates\dashboard.html

``text
{% extends 'base.html' %}
{% block title %}Dashboard · Jardines de la Costa{% endblock %}
{% block content %}
<div class="page-heading"><div><span class="eyebrow">Vista general</span><h1 class="h2 mb-1">Dashboard operativo</h1><p class="text-muted mb-0">Indicadores consolidados desde la operación registrada.</p></div>{% if can_create_project %}<a class="btn btn-primary" href="{{ url_for('projects.project_create') }}"><i class="bi bi-plus-lg me-1"></i>Nuevo proyecto</a>{% endif %}</div>

<div class="row g-3 mb-4">
  <div class="col-6 col-xl-3"><a class="metric-card text-decoration-none" href="{{ url_for(metric_links.active_people) }}"><div class="metric-icon bg-teal"><i class="bi bi-people"></i></div><div><div class="metric-label">Personal activo</div><div class="metric-value">{{ metrics.active_people }}</div><div class="metric-note">empleados y contratistas · Ver detalle</div></div></a></div>
  <div class="col-6 col-xl-3"><a class="metric-card text-decoration-none" href="{{ url_for(metric_links.active_projects) }}"><div class="metric-icon bg-blue"><i class="bi bi-kanban"></i></div><div><div class="metric-label">Proyectos activos</div><div class="metric-value">{{ metrics.active_projects }}</div><div class="metric-note">en ejecución · Ver detalle</div></div></a></div>
  <div class="col-6 col-xl-3"><a class="metric-card text-decoration-none" href="{{ url_for(metric_links.open_incidents) }}"><div class="metric-icon bg-orange"><i class="bi bi-shield-exclamation"></i></div><div><div class="metric-label">Incidentes abiertos</div><div class="metric-value">{{ metrics.open_incidents }}</div><div class="metric-note">pendientes de cierre · Ver detalle</div></div></a></div>
  <div class="col-6 col-xl-3"><a class="metric-card text-decoration-none" href="{{ url_for(metric_links.equipment_due) }}"><div class="metric-icon bg-purple"><i class="bi bi-tools"></i></div><div><div class="metric-label">Mantenimiento próximo</div><div class="metric-value">{{ metrics.equipment_due }}</div><div class="metric-note">próximos 30 días · Ver detalle</div></div></a></div>
</div>

<div class="row g-4">
  <div class="col-12 col-xl-8"><div class="card border-0 shadow-sm h-100"><div class="card-header bg-white d-flex justify-content-between align-items-center"><h2 class="h5 mb-0">Proyectos prioritarios</h2><a href="{{ url_for('projects.project_list') }}" class="small text-decoration-none">Ver todos</a></div><div class="table-responsive"><table class="table align-middle mb-0"><thead><tr><th>Proyecto</th><th>Cliente</th><th>Estado</th><th>Avance / cierre</th></tr></thead><tbody>{% for project in recent_projects %}<tr><td><a class="fw-semibold text-decoration-none" href="{{ url_for('projects.project_detail', project_id=project.id) }}">{{ project.code }} · {{ project.name }}</a></td><td>{{ project.client_name or '—' }}</td><td><span class="status-pill status-{{ project.status }}">{{ project.status|replace('_', ' ')|title }}</span></td><td>{{ project.planned_end_date or 'Sin fecha' }}</td></tr>{% else %}<tr><td colspan="4" class="text-center text-muted py-5">Aún no hay proyectos registrados.</td></tr>{% endfor %}</tbody></table></div></div></div>
  <div class="col-12 col-xl-4"><div class="card border-0 shadow-sm h-100"><div class="card-header bg-white"><h2 class="h5 mb-0">Telemetría reciente</h2></div><div class="card-body p-0"><div class="list-group list-group-flush">{% for event in recent_telemetry %}<div class="list-group-item px-3 py-3 d-flex justify-content-between gap-2"><div><div class="fw-semibold">{{ event.event_type }}</div><div class="small text-muted">{{ event.source_type }} · {{ event.occurred_at }}</div></div><span class="severity severity-{{ event.severity }}">{{ event.severity }}</span></div>{% else %}<div class="p-4 text-center text-muted">Sin eventos recibidos.</div>{% endfor %}</div></div></div></div>
</div>
{% endblock %}

``


## ARCHIVO: app\templates\employees\crew_form.html

``text
{% extends 'base.html' %}
{% block title %}{{ 'Editar' if crew else 'Nueva' }} cuadrilla{% endblock %}
{% set selected_members = members|map(attribute='employee_id')|list %}
{% block content %}<div class="page-heading"><div><span class="eyebrow">Recursos humanos</span><h1 class="h2 mb-0">{{ 'Editar' if crew else 'Nueva' }} cuadrilla</h1></div><a class="btn btn-outline-secondary" href="{{ url_for('employees.crew_list') }}">Volver</a></div><div class="card border-0 shadow-sm"><div class="card-body"><form method="post"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><div class="row g-3"><div class="col-12 col-md-6"><label class="form-label">Nombre de la cuadrilla *</label><input class="form-control" name="name" value="{{ crew.name if crew else '' }}" required></div><div class="col-12 col-md-6"><label class="form-label">Proyecto asignado</label><select class="form-select" name="project_id"><option value="">Sin proyecto</option>{% for project in projects %}<option value="{{ project.id }}" {% if crew and crew.project_id == project.id %}selected{% endif %}>{{ project.code }} · {{ project.name }}</option>{% endfor %}</select></div><div class="col-12 col-md-6"><label class="form-label">Supervisor</label><select class="form-select" name="supervisor_employee_id"><option value="">Sin supervisor</option>{% for supervisor in supervisors %}<option value="{{ supervisor.id }}" {% if crew and crew.supervisor_employee_id == supervisor.id %}selected{% endif %}>{{ supervisor.name }}</option>{% endfor %}</select></div><div class="col-12 col-md-6"><label class="form-label">Estado</label><select class="form-select" name="status"><option value="active" {% if not crew or crew.status == 'active' %}selected{% endif %}>Activa</option><option value="inactive" {% if crew and crew.status == 'inactive' %}selected{% endif %}>Inactiva</option></select></div><div class="col-12"><label class="form-label">Colaboradores</label><select class="form-select" name="employee_ids" multiple size="8">{% for employee in employees %}<option value="{{ employee.id }}" {% if employee.id in selected_members %}selected{% endif %}>{{ employee.name }}{% if employee.position %} · {{ employee.position }}{% endif %}</option>{% endfor %}</select><div class="form-text">Mantén Ctrl o Cmd para seleccionar varios colaboradores.</div></div><div class="col-12"><label class="form-label">Observaciones</label><textarea class="form-control" name="notes" rows="3">{{ crew.notes if crew else '' }}</textarea></div></div><button class="btn btn-primary mt-4">Guardar cuadrilla</button></form></div></div>{% endblock %}

``


## ARCHIVO: app\templates\employees\form.html

``text
{% extends 'base.html' %}
{% if mode == 'employee' %}{% set page_title = 'Empleado' %}{% set back_url = url_for('employees.employee_list') %}{% elif mode == 'contractor' %}{% set page_title = 'Contratista' %}{% set back_url = url_for('employees.contractor_list') %}{% else %}{% set page_title = 'Cuadrilla' %}{% set back_url = url_for('employees.crew_list') %}{% endif %}
{% block title %}{{ 'Editar' if (employee or contractor or crew) else 'Nuevo' }} {{ page_title|lower }}{% endblock %}
{% block content %}
<div class="page-heading"><div><span class="eyebrow">Recursos humanos</span><h1 class="h2 mb-0">{{ 'Editar' if (employee or contractor or crew) else 'Nuevo' }} {{ page_title|lower }}</h1></div><a class="btn btn-outline-secondary" href="{{ back_url }}">Volver</a></div>
<div class="card border-0 shadow-sm"><div class="card-body p-3 p-md-4">
{% if mode == 'employee' %}
<form method="post"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><div class="row g-3">
{% for name,label,catalog in [('document_type','Tipo documento','document_type'),('identification_number','Identificación *',''),('first_name','Nombres *',''),('last_name','Apellidos *','')] %}<div class="col-12 col-md-3"><label class="form-label">{{ label }}</label><input class="form-control" name="{{ name }}" {% if catalog %}data-reference-catalog="{{ catalog }}"{% endif %} value="{{ employee[name] if employee else '' }}" {% if '*' in label %}required{% endif %}></div>{% endfor %}
<div class="col-12 col-md-6"><label class="form-label">Correo</label><input class="form-control" type="email" name="email" value="{{ employee.email if employee else '' }}"></div><div class="col-12 col-md-6"><label class="form-label">Teléfono</label><input class="form-control" name="phone" value="{{ employee.phone if employee else '' }}"></div>
<div class="col-12 col-md-6"><label class="form-label">Cargo</label><input class="form-control" name="position" data-reference-catalog="job_position" value="{{ employee.position if employee else '' }}"></div><div class="col-12 col-md-3"><label class="form-label">Fecha ingreso</label><input class="form-control" type="date" name="hire_date" value="{{ employee.hire_date if employee else '' }}"></div><div class="col-12 col-md-3"><label class="form-label">Estado</label><select class="form-select" name="status">{% for option in ['active','inactive','suspended'] %}<option value="{{ option }}">{{ option|title }}</option>{% endfor %}</select></div>
<div class="col-12 col-md-4"><label class="form-label">Tipo de salario</label><select class="form-select" name="salary_type"><option value="">Seleccionar</option>{% for option in ['monthly','daily','hourly','fee'] %}<option value="{{ option }}">{{ option|title }}</option>{% endfor %}</select></div><div class="col-12 col-md-4"><label class="form-label">Salario base</label><input class="form-control" type="number" min="0" step="0.01" name="base_salary" value="{{ employee.base_salary if employee else '0' }}"></div><div class="col-12 col-md-4"><label class="form-label">Tipo de sangre</label><input class="form-control" name="blood_type" data-reference-catalog="blood_type" value="{{ employee.blood_type if employee else '' }}"></div>
{% for name,label,catalog in [('arl','ARL','arl'),('eps','EPS','eps'),('pension_fund','Fondo de pensiones','pension_fund'),('bank_name','Banco','bank'),('education_level','Nivel educativo','education_level'),('marital_status','Estado civil','marital_status')] %}<div class="col-12 col-md-4"><label class="form-label">{{ label }}</label><input class="form-control" name="{{ name }}" data-reference-catalog="{{ catalog }}" value="{{ employee[name] if employee else '' }}"></div>{% endfor %}
<div class="col-12 col-md-4"><label class="form-label">Número de cuenta</label><input class="form-control" name="bank_account" value="{{ employee.bank_account if employee else '' }}"></div><div class="col-12 col-md-4"><label class="form-label">Contacto de emergencia</label><input class="form-control" name="emergency_contact_name" value="{{ employee.emergency_contact_name if employee else '' }}"></div><div class="col-12 col-md-4"><label class="form-label">Teléfono emergencia</label><input class="form-control" name="emergency_contact_phone" value="{{ employee.emergency_contact_phone if employee else '' }}"></div><div class="col-12 col-md-4"><label class="form-label">Parentesco</label><input class="form-control" name="emergency_contact_relationship" value="{{ employee.emergency_contact_relationship if employee else '' }}"></div>
<div class="col-12"><label class="form-label">Notas</label><textarea class="form-control" name="notes" rows="3">{{ employee.notes if employee else '' }}</textarea></div></div><div class="mt-4 d-flex flex-column flex-sm-row gap-2"><button class="btn btn-primary" type="submit">Guardar empleado</button><a class="btn btn-outline-secondary" href="{{ back_url }}">Cancelar</a></div></form>
{% elif mode == 'contractor' %}<form method="post"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><div class="row g-3"><div class="col-12 col-md-7"><label class="form-label">Razón social *</label><input class="form-control" name="legal_name" required></div><div class="col-12 col-md-5"><label class="form-label">NIT *</label><input class="form-control" name="tax_id" required></div><div class="col-12"><label class="form-label">Notas</label><textarea class="form-control" name="notes"></textarea></div></div><button class="btn btn-primary mt-3">Guardar contratista</button></form>
{% else %}<form method="post"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><label class="form-label">Nombre de la cuadrilla *</label><input class="form-control" name="name" required><button class="btn btn-primary mt-3">Guardar cuadrilla</button></form>{% endif %}
</div></div>
{% endblock %}

``


## ARCHIVO: app\templates\employees\list.html

``text
{% extends 'base.html' %}
{% if mode == 'employees' %}{% set page_title = 'Empleados' %}{% set new_url = url_for('employees.employee_create') %}{% elif mode == 'contractors' %}{% set page_title = 'Contratistas' %}{% set new_url = url_for('employees.contractor_create') %}{% else %}{% set page_title = 'Cuadrillas de campo' %}{% set new_url = url_for('employees.crew_create') %}{% endif %}
{% block title %}{{ page_title }} · RRHH{% endblock %}
{% block content %}
<div class="page-heading"><div><span class="eyebrow">Recursos humanos</span><h1 class="h2 mb-1">{{ page_title }}</h1><p class="text-muted mb-0">{% if can_manage|default(false) %}Registro centralizado y trazable del talento operativo.{% else %}Consulta tus datos personales y documentos asociados.{% endif %}</p></div>{% if can_manage|default(false) %}<a class="btn btn-primary" href="{{ new_url }}"><i class="bi bi-plus-lg me-1"></i>Nuevo registro</a>{% endif %}</div>
{% if can_manage|default(false) %}<div class="d-flex flex-wrap gap-2 mb-3"><a class="btn btn-sm {% if mode == 'employees' %}btn-dark{% else %}btn-outline-secondary{% endif %}" href="{{ url_for('employees.employee_list') }}">Empleados</a><a class="btn btn-sm {% if mode == 'contractors' %}btn-dark{% else %}btn-outline-secondary{% endif %}" href="{{ url_for('employees.contractor_list') }}">Contratistas</a><a class="btn btn-sm {% if mode == 'crews' %}btn-dark{% else %}btn-outline-secondary{% endif %}" href="{{ url_for('employees.crew_list') }}">Cuadrillas</a></div>{% endif %}
<div class="card border-0 shadow-sm"><div class="card-body border-bottom"><form class="row g-2" method="get"><div class="col-12 col-md-6"><label class="visually-hidden" for="q">Buscar</label><input class="form-control" id="q" name="q" value="{{ search|default('') }}" placeholder="Buscar por identificación o nombre"></div><div class="col-12 col-md-auto"><button class="btn btn-outline-secondary" type="submit"><i class="bi bi-search me-1"></i>Buscar</button></div></form></div><div class="table-responsive"><table class="table align-middle mb-0">
{% if mode == 'employees' %}<thead><tr><th>Persona</th><th>Identificación</th><th>Cargo</th><th>EPS / ARL</th><th>Estado</th>{% if can_manage|default(false) %}<th class="text-end">Acciones</th>{% endif %}</tr></thead><tbody>{% for employee in employees %}<tr><td><a class="fw-semibold text-decoration-none" href="{{ url_for('employees.employee_profile', employee_id=employee.id) }}">{{ employee.first_name }} {{ employee.last_name }}</a>{% if employee.email %}<div class="small text-muted">{{ employee.email }}</div>{% endif %}</td><td>{{ employee.identification_number }}</td><td>{{ employee.position or '—' }}</td><td><div>{{ employee.eps_display or '—' }}</div><div class="small text-muted">{{ employee.arl_display or 'ARL no registrada' }}</div></td><td><span class="status-pill status-{{ employee.status }}">{{ employee.status|title }}</span></td>{% if can_manage|default(false) %}<td class="text-end"><a class="btn btn-sm btn-outline-secondary" href="{{ url_for('employees.employee_edit', employee_id=employee.id) }}" aria-label="Editar"><i class="bi bi-pencil"></i></a><form class="d-inline" method="post" action="{{ url_for('employees.employee_delete', employee_id=employee.id) }}" onsubmit="return confirm('¿Confirmas eliminar este empleado? La eliminación será lógica y quedará trazada.');"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><input type="hidden" name="confirm" value="1"><button class="btn btn-sm btn-outline-danger" type="submit" aria-label="Eliminar"><i class="bi bi-trash"></i></button></form></td>{% endif %}</tr>{% else %}<tr><td colspan="6" class="text-center text-muted py-5">No hay empleados que mostrar.</td></tr>{% endfor %}</tbody>
{% elif mode == 'contractors' %}<thead><tr><th>Razón social</th><th>NIT</th><th>Contacto</th><th>Estado</th><th class="text-end">Acciones</th></tr></thead><tbody>{% for contractor in contractors %}<tr><td class="fw-semibold">{{ contractor.legal_name }}</td><td>{{ contractor.tax_id }}</td><td>{{ contractor.contact_name or contractor.email or '—' }}</td><td><span class="status-pill status-{{ contractor.status }}">{{ contractor.status|title }}</span></td><td class="text-end text-nowrap"><a class="btn btn-sm btn-outline-secondary" href="{{ url_for('employees.contractor_edit', contractor_id=contractor.id) }}"><i class="bi bi-pencil"></i></a></td></tr>{% else %}<tr><td colspan="5" class="text-center text-muted py-5">No hay contratistas que mostrar.</td></tr>{% endfor %}</tbody>
{% else %}<thead><tr><th>Cuadrilla</th><th>Supervisor</th><th>Proyecto</th><th>Integrantes</th><th>Estado</th><th class="text-end">Acciones</th></tr></thead><tbody>{% for crew in crews %}<tr><td class="fw-semibold">{{ crew.name }}</td><td>{{ crew.supervisor_name or 'Sin asignar' }}</td><td>{{ crew.project_name or 'Sin proyecto' }}</td><td>{{ crew.member_count }}</td><td><span class="status-pill status-{{ crew.status }}">{{ crew.status|title }}</span></td><td class="text-end text-nowrap"><a class="btn btn-sm btn-outline-secondary" href="{{ url_for('employees.crew_edit', crew_id=crew.id) }}"><i class="bi bi-pencil"></i></a></td></tr>{% else %}<tr><td colspan="6" class="text-center text-muted py-5">No hay cuadrillas que mostrar.</td></tr>{% endfor %}</tbody>{% endif %}
</table></div></div>
{% endblock %}

``


## ARCHIVO: app\templates\employees\profile.html

``text
{% extends 'base.html' %}
{% block title %}Perfil de {{ employee.first_name }}{% endblock %}
{% block content %}
<div class="page-heading"><div class="d-flex align-items-center gap-3"><div class="profile-photo profile-photo-lg">{% if employee.profile_photo %}<img src="{{ url_for('static', filename='uploads/profiles/' ~ employee.profile_photo) }}" alt="Foto de {{ employee.first_name }}">{% else %}<span>{{ employee.first_name[:1] }}{{ employee.last_name[:1] }}</span>{% endif %}</div><div><span class="eyebrow">Talento humano</span><h1 class="h2 mb-1">{{ employee.first_name }} {{ employee.last_name }}</h1><p class="text-muted mb-0">{{ employee.identification_number }} · {{ employee.position or 'Sin cargo asignado' }}</p></div></div><div class="d-flex gap-2"><a class="btn btn-outline-secondary" href="{{ url_for('employees.employee_list') if can_view_all else url_for('main.dashboard') }}">Volver</a>{% if can_manage %}<a class="btn btn-primary" href="{{ url_for('employees.employee_edit', employee_id=employee.id) }}">Editar perfil</a>{% endif %}</div></div>
<div class="row g-3"><div class="col-12 col-lg-5"><div class="card border-0 shadow-sm mb-3"><div class="card-header bg-white"><h2 class="h5 mb-0">Foto de perfil</h2></div><div class="card-body"><form method="post" enctype="multipart/form-data" action="{{ url_for('employees.employee_photo_upload', employee_id=employee.id) }}"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><label class="form-label">Selecciona una imagen</label><input class="form-control" type="file" name="photo" accept="image/png,image/jpeg,image/webp" required><div class="form-text">JPG, PNG o WEBP.</div><button class="btn btn-outline-primary mt-3" type="submit">Actualizar foto</button></form></div></div><div class="card border-0 shadow-sm"><div class="card-header bg-white"><h2 class="h5 mb-0">Datos del colaborador</h2></div><div class="card-body"><dl class="row mb-0"><dt class="col-5">Documento</dt><dd class="col-7">{{ employee.identification_number }}</dd><dt class="col-5">Cargo</dt><dd class="col-7">{{ employee.position or '—' }}</dd><dt class="col-5">Salario base</dt><dd class="col-7">${{ '{:,.0f}'.format(employee.base_salary or 0) }}</dd><dt class="col-5">Tipo de sangre</dt><dd class="col-7">{{ employee.blood_type or '—' }}</dd><dt class="col-5">EPS</dt><dd class="col-7">{{ employee.eps_display or '—' }}</dd><dt class="col-5">ARL</dt><dd class="col-7">{{ employee.arl_display or '—' }}</dd><dt class="col-5">Pensión</dt><dd class="col-7">{{ employee.pension_display or '—' }}</dd><dt class="col-5">Banco</dt><dd class="col-7">{{ employee.bank_display or '—' }}</dd></dl></div></div></div><div class="col-12 col-lg-7"><div class="card border-0 shadow-sm"><div class="card-header bg-white"><h2 class="h5 mb-0">Volantes de pago</h2></div><div class="table-responsive"><table class="table align-middle mb-0"><thead><tr><th>Periodo</th><th>Archivo</th><th class="text-end">Acción</th></tr></thead><tbody>{% for document in documents %}<tr><td>{{ document.period_start }} → {{ document.period_end }}</td><td>{{ document.original_name }}</td><td class="text-end"><a class="btn btn-sm btn-outline-primary" href="{{ url_for('hr.payroll_document', document_id=document.id) }}" target="_blank">Abrir PDF</a></td></tr>{% else %}<tr><td colspan="3" class="text-center text-muted py-4">No hay volantes asociados.</td></tr>{% endfor %}</tbody></table></div></div></div></div>
{% endblock %}

``


## ARCHIVO: app\templates\error.html

``text
{% extends 'base.html' %}
{% block title %}Error {{ code }}{% endblock %}
{% block content %}<div class="empty-state text-center py-5"><div class="display-4 text-muted mb-3">{{ code }}</div><h1 class="h4">{{ message }}</h1><a class="btn btn-primary mt-3" href="{{ url_for('main.index') }}">Volver al inicio</a></div>{% endblock %}

``


## ARCHIVO: app\templates\hr\evaluation_form.html

``text
{% extends 'base.html' %}
{% block title %}Nueva evaluación de desempeño y potencial{% endblock %}
{% block content %}
<div class="page-heading"><div><span class="eyebrow">Talento humano</span><h1 class="h2 mb-0">Nueva evaluación de desempeño y potencial</h1></div><a class="btn btn-outline-secondary" href="{{ url_for('hr.evaluation_list') }}">Volver</a></div>
<div class="alert alert-info border-0 shadow-sm"><i class="bi bi-lightbulb me-1"></i><strong>Instrucciones:</strong> el jefe inmediato debe responder las 10 preguntas con base en hechos observables del periodo.</div>
<form method="post"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><div class="row g-4"><div class="col-12 col-lg-5"><div class="card border-0 shadow-sm"><div class="card-body"><label class="form-label">Colaborador *</label><div class="record-lookup" data-lookup-url="{{ url_for('api.lookup', resource='employees') }}" data-context-url="{{ url_for('api.record_context', resource='employee', record_id=0) }}" data-context-target="#employee-context"><input class="form-control" data-lookup-input placeholder="Buscar por nombre, identificación o cargo" autocomplete="off"><input type="hidden" name="employee_id" required><div class="lookup-results" hidden></div></div><div id="employee-context" hidden></div><label class="form-label mt-3">Fecha</label><input class="form-control" type="date" name="evaluation_date"></div></div></div><div class="col-12 col-lg-7"><div class="card border-0 shadow-sm"><div class="card-body"><h2 class="h5">Encuesta del jefe inmediato</h2><p class="text-muted small">Preguntas 1 a 5: desempeño. Preguntas 6 a 10: potencial. El sistema calculará ambos promedios y ubicará automáticamente al colaborador.</p>{% for question in evaluation_questions %}<div class="mb-3"><label class="form-label">{{ loop.index }}. {{ question }}</label><select class="form-select" name="question_{{ loop.index }}" required><option value="">Seleccionar</option><option value="1">1 — Bajo</option><option value="2">2 — Medio</option><option value="3">3 — Alto</option></select></div>{% endfor %}</div></div></div><div class="col-12"><div class="card border-0 shadow-sm"><div class="card-body"><label class="form-label">Fortalezas observadas y evidencia</label><textarea class="form-control" name="strengths" rows="3"></textarea><label class="form-label mt-3">Plan de desarrollo y seguimiento</label><textarea class="form-control" name="development_plan" rows="3"></textarea><button class="btn btn-primary mt-4" type="submit">Guardar evaluación y generar resultado</button></div></div></div></div></form>
{% endblock %}

``


## ARCHIVO: app\templates\hr\evaluations.html

``text
{% extends 'base.html' %}
{% block title %}Evaluación de desempeño y potencial (9-Box){% endblock %}
{% block content %}
<div class="page-heading"><div><span class="eyebrow">Talento humano</span><h1 class="h2 mb-1">Evaluación de desempeño y potencial (9-Box)</h1><p class="text-muted mb-0">Herramienta para valorar el desempeño actual y el potencial de crecimiento de cada colaborador.</p></div>{% if has_role('rrhh','gerencia','coordinador_operativo','supervisor_operaciones') %}<a class="btn btn-primary" href="{{ url_for('hr.evaluation_create') }}"><i class="bi bi-plus-lg me-1"></i>Nueva evaluación</a>{% endif %}</div>
<div class="card border-0 shadow-sm mb-4"><div class="card-body p-3 p-md-4"><h2 class="h5 mb-2"><i class="bi bi-info-circle text-primary me-2"></i>¿Cómo funciona?</h2><p>El 9-Box cruza dos valoraciones para orientar desarrollo, acompañamiento y sucesión:</p><ol class="mb-0"><li>Selecciona el colaborador y el periodo.</li><li>Valora el <strong>desempeño actual</strong>: resultados, calidad, cumplimiento, seguridad y trabajo en equipo.</li><li>Valora el <strong>potencial de crecimiento</strong>: aprendizaje, autonomía, liderazgo y proyección.</li><li>Registra fortalezas y un plan de desarrollo.</li><li>El sistema cruza ambas calificaciones y ubica a la persona en una de nueve celdas.</li></ol><div class="alert alert-light border mt-3 mb-0"><i class="bi bi-chat-square-text me-1"></i>No es una calificación salarial automática; apoya la retroalimentación y las decisiones de desarrollo.</div></div></div>
<div class="row g-4 mb-4"><div class="col-12 col-lg-7"><div class="card border-0 shadow-sm h-100"><div class="card-header bg-white"><h2 class="h5 mb-0">Matriz de talento</h2></div><div class="card-body"><div class="nine-box"><div class="nine-axis nine-axis-y">Desempeño</div><div class="nine-cell cell-low">Bajo desempeño<br><strong>Bajo potencial</strong></div><div class="nine-cell cell-medium">Bajo desempeño<br><strong>Potencial medio</strong></div><div class="nine-cell cell-high">Bajo desempeño<br><strong>Alto potencial</strong></div><div class="nine-cell cell-low">Desempeño medio<br><strong>Bajo potencial</strong></div><div class="nine-cell cell-medium">Desempeño medio<br><strong>Potencial medio</strong></div><div class="nine-cell cell-high">Desempeño medio<br><strong>Alto potencial</strong></div><div class="nine-cell cell-low">Alto desempeño<br><strong>Bajo potencial</strong></div><div class="nine-cell cell-medium">Alto desempeño<br><strong>Potencial medio</strong></div><div class="nine-cell cell-high">Alto desempeño<br><strong>Alto potencial</strong></div><div class="nine-axis nine-axis-x">Potencial →</div></div></div></div></div><div class="col-12 col-lg-5"><div class="card border-0 shadow-sm h-100"><div class="card-header bg-white"><h2 class="h5 mb-0">Escala</h2></div><div class="card-body small"><p><span class="badge text-bg-danger me-1">1</span> Bajo: requiere plan de mejora y seguimiento.</p><p><span class="badge text-bg-warning me-1">2</span> Medio: cumple parcialmente o está en desarrollo.</p><p><span class="badge text-bg-success me-1">3</span> Alto: desempeño sólido o potencial destacado.</p><p class="text-muted mb-0">La celda queda almacenada en cada evaluación para conservar el histórico.</p></div></div></div></div>
<div class="card border-0 shadow-sm"><div class="table-responsive"><table class="table align-middle mb-0"><thead><tr><th>Persona</th><th>Fecha</th><th>Desempeño</th><th>Potencial</th><th>Celda 9-Box</th><th>Evaluador</th></tr></thead><tbody>{% for evaluation in evaluations %}<tr><td class="fw-semibold">{{ evaluation.employee_name }}</td><td>{{ evaluation.evaluation_date }}</td><td>{{ evaluation.performance_score }}/3</td><td>{{ evaluation.potential_score }}/3</td><td><span class="status-pill status-{% if evaluation.performance_score == 3 and evaluation.potential_score == 3 %}active{% elif evaluation.performance_score == 1 and evaluation.potential_score == 1 %}cancelled{% else %}planning{% endif %}">{{ evaluation.nine_box_cell }}</span></td><td>{{ evaluation.evaluator_name or '—' }}</td></tr>{% else %}<tr><td colspan="6" class="text-center text-muted py-5">No hay evaluaciones registradas.</td></tr>{% endfor %}</tbody></table></div></div>
{% endblock %}

``


## ARCHIVO: app\templates\hr\payroll_detail.html

``text
{% extends 'base.html' %}
{% block title %}Detalle de nómina{% endblock %}
{% block content %}
<div class="page-heading"><div><span class="eyebrow">Nómina</span><h1 class="h2 mb-1">{{ period.period_start }} → {{ period.period_end }}</h1><p class="text-muted mb-0">Estado: {{ period.status|title }}</p></div><div class="d-flex flex-wrap gap-2"><a class="btn btn-outline-secondary" href="{{ url_for('hr.payroll_list') }}">Volver</a><a class="btn btn-outline-primary" href="{{ url_for('hr.payroll_social_security_csv', period_id=period.id) }}">Planilla CSV</a>{% if period.status != 'closed' %}<form method="post" action="{{ url_for('hr.payroll_calculate', period_id=period.id) }}"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><button class="btn btn-primary">Calcular nómina</button></form>{% endif %}</div></div>
<div class="row g-3 mb-4"><div class="col-4"><div class="metric-card"><div class="metric-label">Devengado</div><div class="metric-value">${{ '{:,.0f}'.format(totals.gross) }}</div></div></div><div class="col-4"><div class="metric-card"><div class="metric-label">Deducciones</div><div class="metric-value">${{ '{:,.0f}'.format(totals.deductions) }}</div></div></div><div class="col-4"><div class="metric-card"><div class="metric-label">Neto</div><div class="metric-value">${{ '{:,.0f}'.format(totals.net) }}</div></div></div></div>
<div class="card border-0 shadow-sm mb-4"><div class="card-header bg-white"><h2 class="h5 mb-0">Liquidación individual</h2></div><div class="table-responsive"><table class="table align-middle mb-0"><thead><tr><th>Empleado</th><th>Devengado</th><th>Deducciones</th><th>Neto</th><th>Pago</th></tr></thead><tbody>{% for item in items %}<tr><td>{{ item.employee_name or 'Contratista' }}<div class="small text-muted">{{ item.identification_number or '' }}</div></td><td>${{ '{:,.0f}'.format(item.gross_amount or 0) }}</td><td>${{ '{:,.0f}'.format(item.deductions or 0) }}</td><td>${{ '{:,.0f}'.format(item.net_amount or 0) }}</td><td>{{ item.payment_status|title }}</td></tr>{% else %}<tr><td colspan="5" class="text-center text-muted py-5">Calcula o importa el periodo.</td></tr>{% endfor %}</tbody></table></div></div>
<div class="card border-0 shadow-sm mb-4"><div class="card-header bg-white"><h2 class="h5 mb-0">Importar planilla</h2></div><div class="card-body"><form method="post" enctype="multipart/form-data" action="{{ url_for('hr.payroll_import', period_id=period.id) }}" class="row g-2 align-items-end"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><div class="col-12 col-md-8"><label class="form-label">CSV de planilla</label><input class="form-control" type="file" name="planilla" accept=".csv" required><div class="form-text">identificacion, devengado, deducciones, neto, estado</div></div><div class="col-12 col-md-4"><button class="btn btn-outline-primary w-100">Importar registros</button></div></form></div></div>
<div class="card border-0 shadow-sm mb-4"><div class="card-header bg-white"><h2 class="h5 mb-0">Volantes de pago</h2></div><div class="card-body"><div class="alert alert-info py-2">Este formato contiene dos volantes por página. El sistema recorta cada bloque, lee la cédula y lo distribuye automáticamente.</div><form method="post" enctype="multipart/form-data" action="{{ url_for('hr.payroll_upload_consolidated_slips', period_id=period.id) }}" class="row g-2 align-items-end"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><input type="hidden" name="distribute" value="1"><div class="col-12 col-md-9"><label class="form-label">PDF consolidado</label><input class="form-control" type="file" name="volantes_consolidados" accept="application/pdf,.pdf" required></div><div class="col-12 col-md-3"><button class="btn btn-primary w-100">Recortar y distribuir</button></div></form><div class="table-responsive mt-4"><table class="table table-sm align-middle"><thead><tr><th>Tipo</th><th>Empleado</th><th>Archivo</th><th></th></tr></thead><tbody>{% for document in documents %}<tr><td>{{ 'Individual' if document.document_type == 'pay_stub' else 'Consolidado' }}</td><td>{{ document.employee_name or 'Todos los empleados' }}</td><td>{{ document.original_name }}</td><td class="text-end"><a class="btn btn-sm btn-outline-secondary" href="{{ url_for('hr.payroll_document', document_id=document.id) }}" target="_blank">Abrir</a></td></tr>{% else %}<tr><td colspan="4" class="text-center text-muted py-3">Aún no hay volantes distribuidos.</td></tr>{% endfor %}</tbody></table></div></div></div>
<div class="card border-0 shadow-sm"><div class="card-header bg-white"><h2 class="h5 mb-0">Aportes de seguridad social</h2></div><div class="table-responsive"><table class="table align-middle mb-0"><thead><tr><th>Empleado</th><th>EPS</th><th>Pensión</th><th>ARL</th><th>Caja</th><th>Estado</th></tr></thead><tbody>{% for item in contributions %}<tr><td>{{ item.employee_name or '—' }}</td><td><div class="small">{{ item.eps_name }}</div>${{ '{:,.0f}'.format(item.eps_amount or 0) }}</td><td><div class="small">{{ item.pension_name }}</div>${{ '{:,.0f}'.format(item.pension_amount or 0) }}</td><td><div class="small">{{ item.arl_name }}</div>${{ '{:,.0f}'.format(item.arl_amount or 0) }}</td><td>${{ '{:,.0f}'.format(item.caja_amount or 0) }}</td><td>{{ item.status|title }}</td></tr>{% else %}<tr><td colspan="6" class="text-center text-muted py-4">Sin aportes calculados.</td></tr>{% endfor %}</tbody></table></div></div>
<div class="mt-4">{% if documents|selectattr('document_type', 'equalto', 'pay_stub')|list %}<form method="post" action="{{ url_for('hr.payroll_delete_cut', period_id=period.id) }}" onsubmit="return confirm('¿Eliminar el corte y los volantes individuales generados? El PDF consolidado se conservará.');"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><button class="btn btn-sm btn-outline-danger" type="submit"><i class="bi bi-trash me-1"></i>Eliminar corte y distribución</button></form>{% endif %}</div>
{% endblock %}

``


## ARCHIVO: app\templates\hr\payroll_form.html

``text
{% extends 'base.html' %}
{% block title %}Nuevo periodo de nómina{% endblock %}
{% block content %}
<div class="page-heading"><div><span class="eyebrow">Nómina</span><h1 class="h2 mb-0">Nuevo periodo</h1></div><a class="btn btn-outline-secondary" href="{{ url_for('hr.payroll_list') }}">Volver</a></div>
<div class="row justify-content-center"><div class="col-12 col-lg-8"><div class="card border-0 shadow-sm"><div class="card-body p-3 p-md-4"><form method="post"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><div class="row g-3"><div class="col-12 col-md-6"><label class="form-label">Inicio del periodo *</label><input class="form-control" type="date" name="period_start" required></div><div class="col-12 col-md-6"><label class="form-label">Fin del periodo *</label><input class="form-control" type="date" name="period_end" required></div><div class="col-12 col-md-6"><label class="form-label">Fecha de pago</label><input class="form-control" type="date" name="payment_date"></div><div class="col-12"><label class="form-label">Notas</label><textarea class="form-control" name="notes" rows="3"></textarea></div></div><div class="mt-4 d-flex gap-2"><button class="btn btn-primary" type="submit">Crear periodo</button><a class="btn btn-outline-secondary" href="{{ url_for('hr.payroll_list') }}">Cancelar</a></div></form></div></div></div></div>
{% endblock %}

``


## ARCHIVO: app\templates\hr\payroll_list.html

``text
{% extends 'base.html' %}
{% block title %}Nómina · RRHH{% endblock %}
{% block content %}
<div class="page-heading"><div><span class="eyebrow">Recursos humanos</span><h1 class="h2 mb-1">Nómina y seguridad social</h1><p class="text-muted mb-0">Periodos, liquidación inicial y planillas de aportes.</p></div>{% if has_role('rrhh','asistente_administrativa','gerencia','coordinador_operativo') %}<a class="btn btn-primary" href="{{ url_for('hr.payroll_create') }}"><i class="bi bi-plus-lg me-1"></i>Nuevo periodo</a>{% endif %}</div>
<div class="alert alert-info border-0 small"><i class="bi bi-info-circle me-1"></i>Las tasas del cálculo inicial están centralizadas en <code>app/hr.py</code> y deben ser revisadas por contabilidad antes de una liquidación legal.</div>
<div class="card border-0 shadow-sm"><div class="table-responsive"><table class="table align-middle mb-0"><thead><tr><th>Periodo</th><th>Fecha de pago</th><th>Registros</th><th>Total neto</th><th>Estado</th><th class="text-end">Acciones</th></tr></thead><tbody>{% for period in periods %}<tr><td class="fw-semibold">{{ period.period_start }} → {{ period.period_end }}</td><td>{{ period.payment_date or 'Pendiente' }}</td><td>{{ period.item_count }}</td><td>${{ '{:,.0f}'.format(period.total_net or 0) }}</td><td><span class="status-pill status-{{ period.status }}">{{ period.status|title }}</span></td><td class="text-end"><a class="btn btn-sm btn-outline-secondary" href="{{ url_for('hr.payroll_detail', period_id=period.id) }}">Ver detalle</a></td></tr>{% else %}<tr><td colspan="6" class="text-center text-muted py-5">No hay periodos de nómina.</td></tr>{% endfor %}</tbody></table></div></div>
{% endblock %}

``


## ARCHIVO: app\templates\projects\detail.html

``text
{% extends 'base.html' %}
{% block title %}{{ project.code }} · Proyecto{% endblock %}
{% block content %}
<div class="page-heading"><div><span class="eyebrow">Proyecto {{ project.code }}</span><h1 class="h2 mb-1">{{ project.name }}</h1><p class="text-muted mb-0">{{ project.client_name or 'Cliente sin registrar' }} · {{ project.location or 'Ubicación sin registrar' }}</p></div><div class="d-flex gap-2">{% if has_role('operaciones') %}<a class="btn btn-outline-secondary" href="{{ url_for('projects.project_edit', project_id=project.id) }}"><i class="bi bi-pencil me-1"></i>Editar</a>{% endif %}<a class="btn btn-outline-secondary" href="{{ url_for('projects.project_list') }}">Volver</a></div></div>
<div class="row g-4"><div class="col-12 col-lg-7"><div class="card border-0 shadow-sm mb-4"><div class="card-header bg-white d-flex justify-content-between align-items-center"><h2 class="h5 mb-0">Cronograma y fases</h2><span class="status-pill status-{{ project.status }}">{{ project.status|replace('_',' ')|title }}</span></div><div class="card-body">{% for phase in phases %}<div class="timeline-item"><div class="d-flex justify-content-between gap-2"><div><div class="fw-semibold">{{ phase.sequence }}. {{ phase.name }}</div><div class="small text-muted">{{ phase.planned_start or 'Sin inicio' }} → {{ phase.planned_end or 'Sin fin' }}</div></div><span class="small fw-semibold">{{ phase.progress_percent|round(0)|int }}%</span></div><div class="progress mt-2"><div class="progress-bar bg-teal" style="width:{{ phase.progress_percent }}%"></div></div></div>{% else %}<p class="text-muted mb-0">No hay fases registradas.{% if has_role('operaciones') %} Añade la primera desde el formulario.{% endif %}</p>{% endfor %}</div></div>{% if has_role('operaciones') %}<div class="card border-0 shadow-sm"><div class="card-header bg-white"><h2 class="h5 mb-0">Agregar fase</h2></div><div class="card-body"><form method="post" action="{{ url_for('projects.phase_create', project_id=project.id) }}"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><div class="row g-3"><div class="col-12 col-md-6"><label class="form-label">Nombre *</label><input class="form-control" name="name" required></div><div class="col-6 col-md-2"><label class="form-label">Orden</label><input class="form-control" type="number" min="1" name="sequence" value="{{ (phases|length)+1 }}"></div><div class="col-6 col-md-4"><label class="form-label">Estado</label><select class="form-select" name="status"><option value="pending">Pendiente</option><option value="in_progress">En curso</option><option value="blocked">Bloqueada</option><option value="completed">Completada</option></select></div><div class="col-6 col-md-4"><label class="form-label">Inicio previsto</label><input class="form-control" type="date" name="planned_start"></div><div class="col-6 col-md-4"><label class="form-label">Fin previsto</label><input class="form-control" type="date" name="planned_end"></div><div class="col-12 col-md-4"><label class="form-label">Avance %</label><input class="form-control" type="number" min="0" max="100" name="progress_percent" value="0"></div></div><button class="btn btn-primary mt-3" type="submit">Agregar fase</button></form></div></div>{% endif %}</div>
<div class="col-12 col-lg-5"><div class="card border-0 shadow-sm mb-4"><div class="card-header bg-white"><h2 class="h5 mb-0">Resumen</h2></div><div class="card-body"><dl class="row mb-0"><dt class="col-5 text-muted">Responsable</dt><dd class="col-7">{{ project.manager_name or 'Sin asignar' }}</dd><dt class="col-5 text-muted">Inicio</dt><dd class="col-7">{{ project.start_date or '—' }}</dd><dt class="col-5 text-muted">Fin previsto</dt><dd class="col-7">{{ project.planned_end_date or '—' }}</dd><dt class="col-5 text-muted">Presupuesto</dt><dd class="col-7">${{ '{:,.0f}'.format(project.budget or 0) }}</dd></dl></div></div><div class="card border-0 shadow-sm mb-4"><div class="card-header bg-white"><h2 class="h5 mb-0">Recursos asignados</h2></div><div class="card-body p-0"><div class="list-group list-group-flush">{% for assignment in assignments %}<div class="list-group-item"><div class="fw-semibold">{{ assignment.resource_name }}</div><div class="small text-muted">{{ assignment.role or 'Sin rol definido' }}</div></div>{% else %}<div class="p-4 text-muted">No hay recursos asignados.</div>{% endfor %}</div></div></div>{% if has_role('operaciones') %}<div class="card border-0 shadow-sm"><div class="card-header bg-white"><h2 class="h5 mb-0">Asignar recurso</h2></div><div class="card-body"><form method="post" action="{{ url_for('projects.assignment_create', project_id=project.id) }}"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><div class="mb-2"><label class="form-label">Tipo</label><select class="form-select form-select-sm" name="resource_type" id="resource-type"><option value="employee">Empleado</option><option value="contractor">Contratista</option><option value="crew">Cuadrilla</option></select></div><div class="mb-2"><label class="form-label">Recurso</label><select class="form-select form-select-sm" name="resource_id" id="resource-id" required><optgroup label="Empleados" data-kind="employee">{% for item in employees %}<option value="{{ item.id }}">{{ item.name }}</option>{% endfor %}</optgroup><optgroup label="Contratistas" data-kind="contractor">{% for item in contractors %}<option value="{{ item.id }}">{{ item.name }}</option>{% endfor %}</optgroup><optgroup label="Cuadrillas" data-kind="crew">{% for item in crews %}<option value="{{ item.id }}">{{ item.name }}</option>{% endfor %}</optgroup></select></div><div class="mb-2"><label class="form-label">Rol en el proyecto</label><input class="form-control form-control-sm" name="role" placeholder="Supervisor, operario, proveedor"></div><div class="row g-2"><div class="col-6"><label class="form-label">Desde</label><input class="form-control form-control-sm" type="date" name="assigned_from"></div><div class="col-6"><label class="form-label">Hasta</label><input class="form-control form-control-sm" type="date" name="assigned_to"></div></div><button class="btn btn-sm btn-primary mt-3" type="submit">Asignar</button></form></div></div>{% endif %}</div></div>
{% endblock %}
{% block scripts %}{% if has_role('operaciones') %}<script>const resourceType=document.getElementById('resource-type');const resourceSelect=document.getElementById('resource-id');function filterResources(){const kind=resourceType.value;resourceSelect.querySelectorAll('optgroup').forEach(group=>{const visible=group.dataset.kind===kind;group.hidden=!visible;group.querySelectorAll('option').forEach(option=>option.disabled=!visible);});const first=resourceSelect.querySelector('optgroup:not([hidden]) option');if(first)resourceSelect.value=first.value;}resourceType.addEventListener('change',filterResources);filterResources();</script>{% endif %}{% endblock %}

``


## ARCHIVO: app\templates\projects\form.html

``text
{% extends 'base.html' %}
{% block title %}{{ 'Editar' if project else 'Nuevo' }} proyecto{% endblock %}
{% block content %}
<div class="page-heading"><div><span class="eyebrow">Operaciones</span><h1 class="h2 mb-0">{{ 'Editar' if project else 'Nuevo' }} proyecto</h1></div><a class="btn btn-outline-secondary" href="{{ url_for('projects.project_list') }}">Volver</a></div>
<div class="card border-0 shadow-sm"><div class="card-body p-3 p-md-4"><form method="post"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><div class="row g-3"><div class="col-12 col-md-3"><label class="form-label">Código *</label><input class="form-control" name="code" value="{{ project.code if project else '' }}" placeholder="JDC-2026-001" required></div><div class="col-12 col-md-9"><label class="form-label">Nombre del proyecto *</label><input class="form-control" name="name" value="{{ project.name if project else '' }}" required></div><div class="col-12 col-md-6"><label class="form-label">Cliente</label><input class="form-control" name="client_name" value="{{ project.client_name if project else '' }}"></div><div class="col-12 col-md-6"><label class="form-label">Contacto del cliente</label><input class="form-control" name="client_contact" value="{{ project.client_contact if project else '' }}"></div><div class="col-12"><label class="form-label">Ubicación</label><input class="form-control" name="location" value="{{ project.location if project else '' }}"></div><div class="col-12 col-md-4"><label class="form-label">Inicio</label><input class="form-control" type="date" name="start_date" value="{{ project.start_date if project else '' }}"></div><div class="col-12 col-md-4"><label class="form-label">Fin previsto</label><input class="form-control" type="date" name="planned_end_date" value="{{ project.planned_end_date if project else '' }}"></div>{% if project %}<div class="col-12 col-md-4"><label class="form-label">Fin real</label><input class="form-control" type="date" name="actual_end_date" value="{{ project.actual_end_date if project else '' }}"></div>{% endif %}<div class="col-12 col-md-4"><label class="form-label">Presupuesto</label><input class="form-control" type="number" min="0" step="0.01" name="budget" value="{{ project.budget if project else '0' }}"></div><div class="col-12 col-md-4"><label class="form-label">Estado</label><select class="form-select" name="status">{% for option in ['planning','active','paused','completed','cancelled'] %}<option value="{{ option }}" {% if project and project.status == option %}selected{% endif %}>{{ option|replace('_',' ')|title }}</option>{% endfor %}</select></div><div class="col-12 col-md-4"><label class="form-label">Responsable</label><select class="form-select" name="project_manager_employee_id"><option value="">Sin asignar</option>{% for manager in managers %}<option value="{{ manager.id }}" {% if project and project.project_manager_employee_id == manager.id %}selected{% endif %}>{{ manager.name }}</option>{% endfor %}</select></div><div class="col-12"><label class="form-label">Descripción</label><textarea class="form-control" name="description" rows="4">{{ project.description if project else '' }}</textarea></div></div><div class="mt-4 d-flex flex-column flex-sm-row gap-2"><button class="btn btn-primary" type="submit">Guardar proyecto</button><a class="btn btn-outline-secondary" href="{{ url_for('projects.project_list') }}">Cancelar</a></div></form></div></div>
{% endblock %}

``


## ARCHIVO: app\templates\projects\list.html

``text
{% extends 'base.html' %}
{% block title %}Proyectos · Operaciones{% endblock %}
{% block content %}
<div class="page-heading"><div><span class="eyebrow">Operaciones</span><h1 class="h2 mb-1">Proyectos</h1><p class="text-muted mb-0">Seguimiento de obras, clientes, plazos y responsables.</p></div>{% if has_role('operaciones') %}<a class="btn btn-primary" href="{{ url_for('projects.project_create') }}"><i class="bi bi-plus-lg me-1"></i>Nuevo proyecto</a>{% endif %}</div>
<div class="card border-0 shadow-sm"><div class="table-responsive"><table class="table align-middle mb-0"><thead><tr><th>Proyecto</th><th>Cliente / ubicación</th><th>Avance</th><th>Estado</th><th>Fin previsto</th>{% if has_role('operaciones') %}<th class="text-end">Acciones</th>{% endif %}</tr></thead><tbody>{% for project in projects %}<tr><td><a class="fw-semibold text-decoration-none" href="{{ url_for('projects.project_detail', project_id=project.id) }}">{{ project.code }}</a><div class="small text-muted">{{ project.name }}</div></td><td>{{ project.client_name or '—' }}<div class="small text-muted">{{ project.location or '' }}</div></td><td style="min-width:150px"><div class="d-flex justify-content-between small mb-1"><span>{{ project.progress|round(0)|int }}%</span><span>{{ project.phase_count }} fases</span></div><div class="progress" role="progressbar"><div class="progress-bar bg-teal" style="width:{{ project.progress }}%"></div></div></td><td><span class="status-pill status-{{ project.status }}">{{ project.status|replace('_',' ')|title }}</span></td><td>{{ project.planned_end_date or '—' }}</td>{% if has_role('operaciones') %}<td class="text-end text-nowrap"><a class="btn btn-sm btn-outline-secondary" href="{{ url_for('projects.project_edit', project_id=project.id) }}" aria-label="Editar proyecto"><i class="bi bi-pencil"></i></a><form class="d-inline" method="post" action="{{ url_for('projects.project_delete', project_id=project.id) }}" onsubmit="return confirm('¿Confirmas eliminar este proyecto? La eliminación será lógica.');"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><input type="hidden" name="confirm" value="1"><button class="btn btn-sm btn-outline-danger" type="submit" aria-label="Eliminar proyecto"><i class="bi bi-trash"></i></button></form></td>{% endif %}</tr>{% else %}<tr><td colspan="{% if has_role('operaciones') %}6{% else %}5{% endif %}" class="text-center text-muted py-5">No hay proyectos registrados.</td></tr>{% endfor %}</tbody></table></div></div>
{% endblock %}

``


## ARCHIVO: app\templates\resources\audit_form.html

``text
{% extends 'base.html' %}
{% block title %}Nueva auditoría{% endblock %}
{% block content %}
<div class="page-heading"><div><span class="eyebrow">Control y mejora</span><h1 class="h2 mb-0">Nueva auditoría</h1></div><a class="btn btn-outline-secondary" href="{{ url_for('resources.audits_list') }}">Volver</a></div>
<div class="row justify-content-center"><div class="col-12 col-lg-8"><div class="card border-0 shadow-sm"><div class="card-body p-3 p-md-4"><form method="post"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><div class="row g-3"><div class="col-12 col-md-6"><label class="form-label">Tipo *</label><select class="form-select" name="audit_type"><option value="operational">Operativa</option><option value="sst">SST</option><option value="quality">Calidad</option><option value="environmental">Ambiental</option></select></div><div class="col-12 col-md-6"><label class="form-label">Fecha *</label><input class="form-control" type="date" name="audit_date" required></div><div class="col-12"><label class="form-label">Proyecto</label><select class="form-select" name="project_id"><option value="">Auditoría transversal</option>{% for project in projects %}<option value="{{ project.id }}">{{ project.code }} · {{ project.name }}</option>{% endfor %}</select></div><div class="col-12 col-md-4"><label class="form-label">Puntaje</label><input class="form-control" type="number" min="0" max="100" step="0.1" name="score"></div><div class="col-12"><label class="form-label">Hallazgos</label><textarea class="form-control" name="findings" rows="5"></textarea></div></div><button class="btn btn-primary mt-4" type="submit">Guardar auditoría</button></form></div></div></div></div>
{% endblock %}

``


## ARCHIVO: app\templates\resources\audits.html

``text
{% extends 'base.html' %}
{% block title %}Auditorías · Recursos{% endblock %}
{% block content %}
<div class="page-heading"><div><span class="eyebrow">Control y mejora</span><h1 class="h2 mb-1">Auditorías y planes de acción</h1><p class="text-muted mb-0">Hallazgos operativos, SST y seguimiento de compromisos.</p></div>{% if has_role('operaciones','sst') %}<a class="btn btn-primary" href="{{ url_for('resources.audit_create') }}"><i class="bi bi-plus-lg me-1"></i>Nueva auditoría</a>{% endif %}</div>
<div class="row g-4">{% for audit in audits %}<div class="col-12 col-xl-6"><div class="card border-0 shadow-sm h-100"><div class="card-header bg-white d-flex justify-content-between gap-2"><div><div class="fw-semibold">{{ audit.audit_type|title }} · {{ audit.audit_date }}</div><div class="small text-muted">{{ audit.project_code or 'Auditoría transversal' }} · {{ audit.auditor_name or '—' }}</div></div><span class="status-pill status-{{ audit.status }}">{{ audit.status|title }}</span></div><div class="card-body"><p class="mb-3">{{ audit.findings or 'Sin hallazgos registrados.' }}</p><div class="small text-muted mb-2">Planes abiertos: <strong>{{ audit.open_actions }}</strong></div>{% for plan in plans_by_audit.get(audit.id, []) %}<div class="border rounded-3 p-2 mb-2"><div class="small fw-semibold">{{ plan.description }}</div><div class="d-flex justify-content-between align-items-center gap-2 mt-1"><span class="small text-muted">{{ plan.responsible_name or 'Sin responsable' }} · {{ plan.due_date or 'Sin fecha' }}</span>{% if has_role('operaciones','sst') %}<form method="post" action="{{ url_for('resources.action_plan_status', plan_id=plan.id) }}"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><select class="form-select form-select-sm" name="status" onchange="this.form.submit()"><option value="open" {% if plan.status == 'open' %}selected{% endif %}>Abierto</option><option value="in_progress" {% if plan.status == 'in_progress' %}selected{% endif %}>En curso</option><option value="completed" {% if plan.status == 'completed' %}selected{% endif %}>Completado</option><option value="overdue" {% if plan.status == 'overdue' %}selected{% endif %}>Vencido</option></select></form>{% endif %}</div></div>{% endfor %}{% if has_role('operaciones','sst') %}<form method="post" action="{{ url_for('resources.action_plan_create', audit_id=audit.id) }}"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><div class="row g-2"><div class="col-12"><input class="form-control form-control-sm" name="description" placeholder="Nuevo plan de acción" required></div><div class="col-7"><select class="form-select form-select-sm" name="responsible_employee_id"><option value="">Responsable</option>{% for employee in employees %}<option value="{{ employee.id }}">{{ employee.name }}</option>{% endfor %}</select></div><div class="col-5"><input class="form-control form-control-sm" type="date" name="due_date"></div><div class="col-12"><button class="btn btn-sm btn-outline-primary" type="submit">Agregar plan</button></div></div></form>{% endif %}</div></div></div>{% else %}<div class="col-12"><div class="empty-state text-center text-muted py-5">No hay auditorías registradas.</div></div>{% endfor %}</div>
{% endblock %}

``


## ARCHIVO: app\templates\resources\equipment_form.html

``text
{% extends 'base.html' %}
{% block title %}Nuevo equipo{% endblock %}
{% block content %}
<div class="page-heading"><div><span class="eyebrow">Recursos</span><h1 class="h2 mb-0">Nuevo equipo o maquinaria</h1></div><a class="btn btn-outline-secondary" href="{{ url_for('resources.equipment_list') }}">Volver</a></div>
<div class="row justify-content-center"><div class="col-12 col-lg-9"><div class="card border-0 shadow-sm"><div class="card-body p-3 p-md-4"><form method="post"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><div class="row g-3"><div class="col-12 col-md-4"><label class="form-label">Código de activo *</label><input class="form-control" name="asset_code" required></div><div class="col-12 col-md-8"><label class="form-label">Nombre *</label><input class="form-control" name="name" required></div><div class="col-12 col-md-4"><label class="form-label">Tipo</label><input class="form-control" name="equipment_type"></div><div class="col-12 col-md-4"><label class="form-label">Marca</label><input class="form-control" name="brand"></div><div class="col-12 col-md-4"><label class="form-label">Modelo</label><input class="form-control" name="model"></div><div class="col-12 col-md-6"><label class="form-label">Número de serie</label><input class="form-control" name="serial_number"></div><div class="col-12 col-md-6"><label class="form-label">Ubicación</label><input class="form-control" name="location"></div><div class="col-12 col-md-4"><label class="form-label">Estado</label><select class="form-select" name="status"><option value="available">Disponible</option><option value="assigned">Asignado</option><option value="maintenance">Mantenimiento</option><option value="out_of_service">Fuera de servicio</option></select></div><div class="col-12 col-md-4"><label class="form-label">Proyecto</label><select class="form-select" name="project_id"><option value="">Sin asignar</option>{% for project in projects %}<option value="{{ project.id }}">{{ project.code }} · {{ project.name }}</option>{% endfor %}</select></div><div class="col-12 col-md-4"><label class="form-label">Próximo servicio</label><input class="form-control" type="date" name="next_service_date"></div><div class="col-12"><label class="form-label">Notas</label><textarea class="form-control" name="notes" rows="3"></textarea></div></div><button class="btn btn-primary mt-4" type="submit">Guardar equipo</button></form></div></div></div></div>
{% endblock %}

``


## ARCHIVO: app\templates\resources\equipment.html

``text
{% extends 'base.html' %}
{% block title %}Maquinaria · Recursos{% endblock %}
{% block content %}
<div class="page-heading"><div><span class="eyebrow">Control de recursos</span><h1 class="h2 mb-1">Maquinaria y equipos</h1><p class="text-muted mb-0">Estado, ubicación y mantenimiento preventivo.</p></div>{% if has_role('operaciones') %}<a class="btn btn-primary" href="{{ url_for('resources.equipment_create') }}"><i class="bi bi-plus-lg me-1"></i>Nuevo equipo</a>{% endif %}</div>
<div class="card border-0 shadow-sm"><div class="table-responsive"><table class="table align-middle mb-0"><thead><tr><th>Activo</th><th>Tipo / marca</th><th>Estado</th><th>Ubicación</th><th>Próximo servicio</th>{% if has_role('operaciones') %}<th class="text-end">Programar</th>{% endif %}</tr></thead><tbody>{% for item in equipment %}<tr><td><div class="fw-semibold">{{ item.name }}</div><div class="small text-muted">{{ item.asset_code }}{% if item.serial_number %} · {{ item.serial_number }}{% endif %}</div></td><td>{{ item.equipment_type or '—' }}{% if item.brand %}<div class="small text-muted">{{ item.brand }} {{ item.model or '' }}</div>{% endif %}</td><td><span class="status-pill status-{{ item.status }}">{{ item.status|replace('_',' ')|title }}</span></td><td>{{ item.location or item.project_code or 'Sin asignar' }}</td><td>{{ item.next_service_date or 'Sin fecha' }}</td>{% if has_role('operaciones') %}<td class="text-end"><form class="d-flex flex-column flex-sm-row gap-1 justify-content-end" method="post" action="{{ url_for('resources.maintenance_create', equipment_id=item.id) }}"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><input class="form-control form-control-sm" type="date" name="scheduled_date" required><select class="form-select form-select-sm" name="maintenance_type"><option value="preventive">Preventivo</option><option value="corrective">Correctivo</option><option value="inspection">Inspección</option></select><button class="btn btn-sm btn-outline-primary" type="submit">Programar</button></form></td>{% endif %}</tr>{% else %}<tr><td colspan="{% if has_role('operaciones') %}6{% else %}5{% endif %}" class="text-center text-muted py-5">No hay maquinaria registrada.</td></tr>{% endfor %}</tbody></table></div></div>
{% endblock %}

``


## ARCHIVO: app\templates\resources\material_form.html

``text
{% extends 'base.html' %}
{% block title %}Nuevo material{% endblock %}
{% block content %}
<div class="page-heading"><div><span class="eyebrow">Recursos</span><h1 class="h2 mb-0">Nuevo material</h1></div><a class="btn btn-outline-secondary" href="{{ url_for('resources.materials_list') }}">Volver</a></div>
<div class="row justify-content-center"><div class="col-12 col-lg-8"><div class="card border-0 shadow-sm"><div class="card-body p-3 p-md-4"><form method="post"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><div class="row g-3"><div class="col-12 col-md-4"><label class="form-label">SKU *</label><input class="form-control" name="sku" required></div><div class="col-12 col-md-8"><label class="form-label">Nombre *</label><input class="form-control" name="name" required></div><div class="col-12 col-md-4"><label class="form-label">Unidad *</label><input class="form-control" name="unit" placeholder="kg, unidad, m3" required></div><div class="col-12 col-md-4"><label class="form-label">Stock mínimo</label><input class="form-control" type="number" min="0" step="0.01" name="minimum_stock" value="0"></div><div class="col-12 col-md-4"><label class="form-label">Stock inicial</label><input class="form-control" type="number" min="0" step="0.01" name="current_stock" value="0"></div><div class="col-12 col-md-6"><label class="form-label">Costo unitario</label><input class="form-control" type="number" min="0" step="0.01" name="unit_cost" value="0"></div><div class="col-12 col-md-6"><label class="form-label">Proveedor</label><input class="form-control" name="supplier"></div></div><button class="btn btn-primary mt-4" type="submit">Guardar material</button></form></div></div></div></div>
{% endblock %}

``


## ARCHIVO: app\templates\resources\materials.html

``text
{% extends 'base.html' %}
{% block title %}Materiales · Recursos{% endblock %}
{% block content %}
<div class="page-heading"><div><span class="eyebrow">Control de recursos</span><h1 class="h2 mb-1">Materiales</h1><p class="text-muted mb-0">Inventario, existencias y movimientos por operación.</p></div>{% if has_role('operaciones') %}<a class="btn btn-primary" href="{{ url_for('resources.material_create') }}"><i class="bi bi-plus-lg me-1"></i>Nuevo material</a>{% endif %}</div>
<div class="card border-0 shadow-sm"><div class="table-responsive"><table class="table align-middle mb-0"><thead><tr><th>Material</th><th>Unidad</th><th>Existencia</th><th>Mínimo</th><th>Costo unitario</th>{% if has_role('operaciones') %}<th class="text-end">Movimiento</th>{% endif %}</tr></thead><tbody>{% for material in materials %}<tr><td><div class="fw-semibold">{{ material.name }}</div><div class="small text-muted">{{ material.sku }}{% if material.supplier %} · {{ material.supplier }}{% endif %}</div></td><td>{{ material.unit }}</td><td><span class="status-pill {% if material.current_stock <= material.minimum_stock %}status-paused{% else %}status-active{% endif %}">{{ material.current_stock }}</span></td><td>{{ material.minimum_stock }}</td><td>${{ '{:,.0f}'.format(material.unit_cost or 0) }}</td>{% if has_role('operaciones') %}<td class="text-end"><form class="d-flex flex-column flex-sm-row gap-1 justify-content-end" method="post" action="{{ url_for('resources.material_movement', material_id=material.id) }}"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><select class="form-select form-select-sm" name="movement_type" aria-label="Tipo"><option value="in">Entrada</option><option value="out">Salida</option><option value="return">Devolución</option></select><input class="form-control form-control-sm movement-qty" type="number" min="0.01" step="0.01" name="quantity" placeholder="Cantidad" required><button class="btn btn-sm btn-outline-primary" type="submit">Aplicar</button></form></td>{% endif %}</tr>{% else %}<tr><td colspan="{% if has_role('operaciones') %}6{% else %}5{% endif %}" class="text-center text-muted py-5">No hay materiales registrados.</td></tr>{% endfor %}</tbody></table></div></div>
{% endblock %}

``


## ARCHIVO: app\templates\sst\dashboard.html

``text
{% extends 'base.html' %}
{% block title %}SST / HSE · Dashboard{% endblock %}
{% block content %}
<div class="page-heading"><div><span class="eyebrow">Seguridad y salud en el trabajo</span><h1 class="h2 mb-1">Dashboard SST / HSE</h1><p class="text-muted mb-0">Cumplimiento, incidentes y eventos recibidos desde campo.</p></div>{% if has_role('sst','operaciones') %}<div class="d-flex flex-wrap gap-2"><a class="btn btn-outline-danger" href="{{ url_for('sst.incident_create') }}"><i class="bi bi-exclamation-triangle me-1"></i>Reportar incidente</a><a class="btn btn-primary" href="{{ url_for('sst.inspection_create') }}"><i class="bi bi-clipboard2-check me-1"></i>Nueva inspección</a></div>{% endif %}</div>
<div class="row g-3 mb-4"><div class="col-6 col-xl-3"><a class="metric-card text-decoration-none" href="{{ url_for('resources.audits_list') }}"><div class="metric-icon bg-teal"><i class="bi bi-clipboard2-check"></i></div><div><div class="metric-label">Cumplimiento</div><div class="metric-value">{{ data.compliance_percent }}%</div><div class="metric-note">promedio de inspecciones</div></div></a></div><div class="col-6 col-xl-3"><a class="metric-card text-decoration-none" href="{{ url_for('sst.dashboard') }}#incidentes"><div class="metric-icon bg-orange"><i class="bi bi-exclamation-triangle"></i></div><div><div class="metric-label">Incidentes abiertos</div><div class="metric-value">{{ data.open_incidents }}</div><div class="metric-note">requieren seguimiento</div></div></a></div><div class="col-6 col-xl-3"><a class="metric-card text-decoration-none" href="{{ url_for('sst.dashboard') }}#telemetria"><div class="metric-icon bg-red"><i class="bi bi-broadcast-pin"></i></div><div><div class="metric-label">Eventos críticos</div><div class="metric-value">{{ data.critical_events_30d }}</div><div class="metric-note">últimos 30 días</div></div></a></div><div class="col-6 col-xl-3"><a class="metric-card text-decoration-none" href="{{ url_for('sst.dashboard') }}#inspecciones"><div class="metric-icon bg-blue"><i class="bi bi-calendar2-check"></i></div><div><div class="metric-label">Inspecciones</div><div class="metric-value">{{ data.inspections_30d }}</div><div class="metric-note">últimos 30 días</div></div></a></div></div>
<div class="row g-4 mb-4"><div class="col-12 col-xl-6" id="inspecciones"><div class="card border-0 shadow-sm h-100"><div class="card-header bg-white"><h2 class="h5 mb-0">Inspecciones recientes</h2></div><div class="table-responsive"><table class="table align-middle mb-0"><thead><tr><th>Fecha</th><th>Proyecto</th><th>Cumplimiento</th><th>Estado</th></tr></thead><tbody>{% for inspection in data.recent_inspections %}<tr><td>{{ inspection.inspection_date }}</td><td>{{ inspection.project_code or 'Transversal' }}</td><td class="fw-semibold">{{ inspection.compliance_percent }}%</td><td><span class="status-pill status-{{ inspection.status }}">{{ inspection.status|title }}</span></td></tr>{% else %}<tr><td colspan="4" class="text-center text-muted py-4">Sin inspecciones registradas.</td></tr>{% endfor %}</tbody></table></div></div></div><div class="col-12 col-xl-6" id="incidentes"><div class="card border-0 shadow-sm h-100"><div class="card-header bg-white"><h2 class="h5 mb-0">Incidentes recientes</h2></div><div class="table-responsive"><table class="table align-middle mb-0"><thead><tr><th>Fecha</th><th>Tipo</th><th>Severidad</th><th>Estado</th></tr></thead><tbody>{% for incident in data.recent_incidents %}<tr><td>{{ incident.occurred_at }}</td><td>{{ incident.incident_type|replace('_',' ')|title }}</td><td><span class="severity severity-{{ incident.severity }}">{{ incident.severity }}</span></td><td>{% if has_role('sst','operaciones') %}<form method="post" action="{{ url_for('sst.incident_status', incident_id=incident.id) }}"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><select class="form-select form-select-sm" name="status" onchange="this.form.submit()"><option value="open" {% if incident.status == 'open' %}selected{% endif %}>Abierto</option><option value="investigating" {% if incident.status == 'investigating' %}selected{% endif %}>En investigación</option><option value="closed" {% if incident.status == 'closed' %}selected{% endif %}>Cerrado</option></select></form>{% else %}<span class="status-pill status-{{ incident.status }}">{{ incident.status|replace('_',' ')|title }}</span>{% endif %}</td></tr>{% else %}<tr><td colspan="4" class="text-center text-muted py-4">Sin incidentes registrados.</td></tr>{% endfor %}</tbody></table></div></div></div></div>
<div class="card border-0 shadow-sm" id="telemetria"><div class="card-header bg-white"><h2 class="h5 mb-0">Eventos de telemetría en vivo</h2></div><div class="table-responsive"><table class="table align-middle mb-0"><thead><tr><th>Origen</th><th>Evento</th><th>Severidad</th><th>Ocurrió</th><th>Recibido</th></tr></thead><tbody>{% for event in data.recent_events %}<tr><td>{{ event.source_type }}{% if event.device_id %}<div class="small text-muted">{{ event.device_id }}</div>{% endif %}</td><td class="fw-semibold">{{ event.event_type }}</td><td><span class="severity severity-{{ event.severity }}">{{ event.severity }}</span></td><td>{{ event.occurred_at }}</td><td>{{ event.received_at }}</td></tr>{% else %}<tr><td colspan="5" class="text-center text-muted py-5">No se han recibido eventos de campo todavía.</td></tr>{% endfor %}</tbody></table></div></div>
{% endblock %}

``


## ARCHIVO: app\templates\sst\incident_form.html

``text
{% extends 'base.html' %}
{% block title %}Reportar incidente SST{% endblock %}
{% block content %}
<div class="page-heading"><div><span class="eyebrow">SST / HSE</span><h1 class="h2 mb-0">Reportar incidente</h1></div><a class="btn btn-outline-secondary" href="{{ url_for('sst.dashboard') }}">Volver</a></div>
<div class="row justify-content-center"><div class="col-12 col-lg-8"><div class="card border-0 shadow-sm"><div class="card-body p-3 p-md-4"><form method="post"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><div class="row g-3"><div class="col-12 col-md-6"><label class="form-label">Fecha y hora *</label><input class="form-control" type="datetime-local" name="occurred_at" required></div><div class="col-12 col-md-6"><label class="form-label">Proyecto</label><div class="record-lookup" data-lookup-url="{{ url_for('api.lookup', resource='projects') }}" data-context-url="{{ url_for('api.record_context', resource='project', record_id=0) }}" data-context-target="#project-context"><input class="form-control" data-lookup-input placeholder="Buscar código, cliente o ubicación" autocomplete="off"><input type="hidden" name="project_id"><div class="lookup-results" hidden></div></div><div id="project-context" hidden></div></div><div class="col-12 col-md-4"><label class="form-label">Tipo *</label><select class="form-select" name="incident_type"><option value="near_miss">Casi accidente</option><option value="accident">Accidente</option><option value="illness">Enfermedad</option><option value="unsafe_condition">Condición insegura</option></select></div><div class="col-12 col-md-4"><label class="form-label">Severidad *</label><select class="form-select" name="severity"><option value="low">Baja</option><option value="medium" selected>Media</option><option value="high">Alta</option><option value="critical">Crítica</option></select></div><div class="col-12 col-md-4"><label class="form-label">Persona involucrada</label><input class="form-control form-control-sm mb-2" data-select-filter="#incident-employee" placeholder="Filtrar persona"><select class="form-select" id="incident-employee" name="employee_id"><option value="">No especificada</option>{% for employee in employees %}<option value="{{ employee.id }}">{{ employee.name }}</option>{% endfor %}</select></div><div class="col-12"><label class="form-label">Descripción *</label><textarea class="form-control" name="description" rows="5" required></textarea></div></div><button class="btn btn-danger mt-4" type="submit">Registrar incidente</button></form></div></div></div></div>
{% endblock %}

``


## ARCHIVO: app\templates\sst\inspection_form.html

``text
{% extends 'base.html' %}
{% block title %}Nueva inspección SST{% endblock %}
{% block content %}
<div class="page-heading"><div><span class="eyebrow">SST / HSE</span><h1 class="h2 mb-0">Nueva inspección</h1></div><a class="btn btn-outline-secondary" href="{{ url_for('sst.dashboard') }}">Volver</a></div>
<div class="row justify-content-center"><div class="col-12 col-lg-8"><div class="card border-0 shadow-sm"><div class="card-body p-3 p-md-4"><form method="post"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><div class="row g-3"><div class="col-12 col-md-6"><label class="form-label">Fecha *</label><input class="form-control" type="date" name="inspection_date" required></div><div class="col-12 col-md-6"><label class="form-label">Proyecto</label><div class="record-lookup" data-lookup-url="{{ url_for('api.lookup', resource='projects') }}" data-context-url="{{ url_for('api.record_context', resource='project', record_id=0) }}" data-context-target="#project-context"><input class="form-control" data-lookup-input placeholder="Buscar código, cliente o ubicación" autocomplete="off"><input type="hidden" name="project_id"><div class="lookup-results" hidden></div></div><div id="project-context" hidden></div></div><div class="col-12 col-md-6"><label class="form-label">Cumplimiento (%) *</label><input class="form-control" type="number" min="0" max="100" step="0.1" name="compliance_percent" required></div><div class="col-12 col-md-6"><label class="form-label">Estado</label><select class="form-select" name="status"><option value="open">Abierta</option><option value="closed">Cerrada</option></select></div><div class="col-12"><label class="form-label">Hallazgos y observaciones</label><textarea class="form-control" name="findings" rows="5"></textarea></div></div><button class="btn btn-primary mt-4" type="submit">Guardar inspección</button></form></div></div></div></div>
{% endblock %}

``


## ARCHIVO: app\utils.py

``text
import hmac
import secrets
from functools import wraps

from flask import abort, g, redirect, request, session, url_for


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def validate_csrf():
    expected = session.get("csrf_token")
    supplied = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
    return bool(expected and supplied and hmac.compare_digest(expected, supplied))


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.get("user") is None:
            if request.is_json or request.path.startswith("/api/"):
                abort(401)
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped_view


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            current_roles = {row["name"] for row in g.get("user_roles", [])}
            # El coordinador operativo gestiona la operación y el talento a su cargo,
            # pero nunca obtiene permisos de administración del sistema.
            if "coordinador_operativo" in current_roles and "admin" not in roles:
                return view(*args, **kwargs)
            if "operaciones" in roles:
                if current_roles.intersection({"supervisor_operaciones", "coordinador_operativo"}):
                    current_roles.add("operaciones")
            if "sst" in roles:
                if current_roles.intersection({"supervisor_sst"}):
                    current_roles.add("sst")
            if not current_roles.intersection(roles):
                abort(403)
            return view(*args, **kwargs)

        return wrapped_view

    return decorator


DELETE_TARGETS = {
    "employees": ("employees", "id"),
    "contractors": ("contractors", "id"),
    "crews": ("crews", "id"),
    "projects": ("projects", "id"),
    "materials": ("materials", "id"),
    "equipment": ("equipment", "id"),
}


def delete_confirmation(request_data):
    if hasattr(request_data, "get_json"):
        if request_data.is_json:
            payload = request_data.get_json(silent=True) or {}
            return str(payload.get("confirm", "")) == "1"
        return str(request_data.form.get("confirm", "")) == "1"
    return str(request_data.get("confirm", "")) == "1"


def soft_delete_entity(resource, record_id):
    from flask import g

    from .db import execute

    target = DELETE_TARGETS.get(resource)
    if not target:
        return False
    table, key = target
    cursor = execute(
        f"UPDATE {table} SET deleted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE {key} = ? AND deleted_at IS NULL",
        (record_id,),
    )
    if cursor.rowcount == 1:
        current_user = g.get("user")
        execute(
            "INSERT INTO audit_log (user_id, action, entity_type, entity_id, metadata_json) VALUES (?, ?, ?, ?, ?)",
            (current_user["id"] if current_user else None, "soft_delete", resource, record_id, None),
        )
        return True
    return False

``
