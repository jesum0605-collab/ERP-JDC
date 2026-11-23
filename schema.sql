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
    must_change_password INTEGER NOT NULL DEFAULT 0 CHECK (must_change_password IN (0, 1)),
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
    pay_frequency TEXT NOT NULL DEFAULT 'biweekly' CHECK (pay_frequency IN ('monthly', 'biweekly', 'daily', 'hourly')),
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
    assigned_driver_employee_id INTEGER REFERENCES employees(id) ON DELETE SET NULL,
    vehicle_restrictions TEXT,
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

CREATE TABLE IF NOT EXISTS driver_employee_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    driver_employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (driver_employee_id, employee_id, project_id)
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
    base_salary_amount NUMERIC NOT NULL DEFAULT 0 CHECK (base_salary_amount >= 0),
    total_base_amount NUMERIC NOT NULL DEFAULT 0 CHECK (total_base_amount >= 0),
    biweekly_salary_amount NUMERIC NOT NULL DEFAULT 0 CHECK (biweekly_salary_amount >= 0),
    transport_subsidy_amount NUMERIC NOT NULL DEFAULT 0 CHECK (transport_subsidy_amount >= 0),
    overtime_amount NUMERIC NOT NULL DEFAULT 0 CHECK (overtime_amount >= 0),
    other_earnings_amount NUMERIC NOT NULL DEFAULT 0 CHECK (other_earnings_amount >= 0),
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
    field_mapping TEXT,
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

CREATE TABLE IF NOT EXISTS document_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    original_name TEXT NOT NULL,
    stored_name TEXT NOT NULL UNIQUE,
    mime_type TEXT,
    uploaded_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1))
);

CREATE TABLE IF NOT EXISTS generated_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id INTEGER NOT NULL REFERENCES document_templates(id) ON DELETE RESTRICT,
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    original_name TEXT NOT NULL,
    stored_name TEXT NOT NULL UNIQUE,
    generated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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
    report_type TEXT NOT NULL DEFAULT 'sst_incident',
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
    module TEXT NOT NULL DEFAULT 'system',
    entity_type TEXT NOT NULL,
    entity_id INTEGER,
    result TEXT NOT NULL DEFAULT 'success' CHECK (result IN ('success', 'failure', 'rejected')),
    reason TEXT,
    before_json TEXT,
    after_json TEXT,
    correlation_id TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_log_entity ON audit_log(entity_type, entity_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_log_actor ON audit_log(user_id, created_at);

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
