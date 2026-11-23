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

La versión canónica del código es la carpeta `app/` junto con `tests/`, `run.py` y `instance/`. La carpeta `jardines-erp-codigo-fuente/` es una copia histórica/exportada y no debe modificarse para nuevas funcionalidades; mantener ambas versiones sincronizadas puede causar despliegues inconsistentes.

Ya están disponibles las pantallas iniciales y rutas de escritura para nómina, aportes de seguridad social, evaluación 9-Box, inventario de materiales, programación de mantenimiento, auditorías y planes de acción. El cálculo de nómina usa tasas configurables en `app/hr.py`; debe ser revisado y parametrizado por contabilidad conforme al periodo y normativa aplicable antes de usarlo para pagos reales.

Los formularios SST y evaluación 9-Box ya usan búsqueda remota y muestran información relacionada al seleccionar un proyecto o empleado. Los selectores largos de otros formularios incorporan filtrado local automático.

La siguiente etapa puede incorporar permisos por acción más detallados, firma/aprobación de planillas, integración contable, carga documental y notificaciones automáticas.
