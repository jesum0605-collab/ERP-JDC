# Fase 4.1 — Auditoría integral implementada

## Diseño

La auditoría usa la tabla existente `audit_log` y un único helper centralizado, `audit_event()`. Cada evento registra actor, acción, módulo, entidad, resultado, motivo, estado anterior/posterior, metadatos sanitizados y `correlation_id`. Los secretos, contraseñas, tokens, claves API y datos bancarios completos se redactan antes de persistirse.

Los eventos se escriben dentro de `transaction()` cuando la operación es compuesta. Fuera de una transacción explícita, el evento se confirma inmediatamente después de la operación individual. No existe una ruta de modificación o eliminación de auditoría.

## Archivos modificados

- `schema.sql`: columnas y consultas de índice para auditoría.
- `app/db.py`: migración aditiva, `PRAGMA foreign_keys=ON`, control transaccional y `transaction()`.
- `app/utils.py`: sanitización y `audit_event()`; eliminación lógica auditada.
- `app/admin.py` y `app/templates/admin/audit.html`: consulta protegida para administración/gerencia.
- `app/employees.py`: creación, actualización y fotografía de colaboradores.
- `app/projects.py`: proyectos, fases y asignaciones.
- `app/resources.py`: materiales, movimientos, maquinaria, mantenimientos, auditorías y planes.
- `app/sst.py`: inspecciones, incidentes, estados, API de incidentes y telemetría.
- `app/hr.py`: períodos, importaciones, volantes, cálculo, cierre, eliminación y evaluaciones 9-Box.
- `app/documents.py`: plantillas, archivado/eliminación y documentos generados.
- `app/templates/base.html`: acceso visible a la auditoría para administradores.

## Operaciones cubiertas

Usuarios y roles, colaboradores, proyectos y asignaciones, inventario y movimientos, maquinaria y mantenimientos, SST/HSE, planes de acción, nómina y soportes importados, evaluaciones 9-Box, plantillas y documentos generados, además de eliminaciones lógicas universales.

## Migración y datos

La migración es aditiva: agrega columnas e índices únicamente cuando faltan. No elimina tablas ni registros históricos. Se creó un respaldo local previo en `instance/backups/` antes de activar la migración sobre la base de desarrollo.

## Pruebas ejecutadas

- Compilación: `\.venv\Scripts\python.exe -m compileall -q app` — OK.
- Suite existente: `\.venv\Scripts\python.exe -m unittest tests.test_core -q` — 6 pruebas, OK.
- Sanitización: contraseñas/tokens no aparecen en el JSON de auditoría — OK.
- Rollback: un evento creado dentro de `transaction()` desaparece tras excepción — OK.
- Base local: columnas de auditoría presentes y conexiones de la aplicación con `foreign_keys=1` — OK.

## Pendientes y límites

- Las operaciones que escriben archivos físicos y base de datos no pueden revertir físicamente un archivo con SQLite. El código registra éxito únicamente después de crear el archivo y antes de insertar el registro; una limpieza compensatoria adicional sería una mejora posterior.
- La distribución de volantes consolidados mantiene el procesamiento por bloques; sus escrituras de archivos y registros quedan documentadas, pero requieren una estrategia de staging/compensación si se exige atomicidad física completa.
- Las operaciones rechazadas por autorización o validación no generan un evento de éxito; permanecen en el log de aplicación HTTP. Registrar cada rechazo como evento de auditoría es una ampliación separable.
