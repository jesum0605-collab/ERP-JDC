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
