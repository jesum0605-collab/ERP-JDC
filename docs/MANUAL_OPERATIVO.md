# Jardines de la Costa ERP — Manual operativo

## Acceso

El usuario de colaboradores es su número de documento. Las cuentas nuevas o restablecidas deben cambiar la clave provisional en el primer ingreso. El administrador puede reestablecer credenciales desde **Usuarios y permisos**.

## Roles

- **Administrador:** configuración, usuarios, permisos y todos los módulos.
- **Gerencia:** consulta y control ejecutivo, proyectos, auditorías y talento.
- **Coordinador operativo:** proyectos, cuadrillas, asignaciones, evaluaciones, auditorías y seguimiento operativo; no administra usuarios ni credenciales.
- **Supervisor de operaciones:** operación de sus cuadrillas, proyectos, auditorías y evaluaciones autorizadas.
- **Supervisor SST / SST:** inspecciones, incidentes, cumplimiento y planes de acción SST.
- **Asistente administrativa / RR. HH.:** empleados, documentos, nómina y soportes.
- **Conductor:** panel propio, novedades de conducción, vehículo y datos asignados.
- **Jardinero:** perfil propio, información laboral y funciones operativas habilitadas.

Los módulos no autorizados se ocultan del menú y, si se intenta acceder directamente, responden con 403.

## Evaluación 9-Box

El jefe inmediato abre **Desempeño 9-Box**, selecciona el colaborador y responde diez preguntas de selección múltiple. Las preguntas 1–5 calculan desempeño; las 6–10 calculan potencial. Cada dimensión queda en escala 1–3 y el cruce ubica al colaborador en una de nueve celdas. La fecha identifica el mes y el historial se conserva para comparar evolución mensual.

## Proyectos y operación

Cada proyecto debe tener código, cliente, fechas y estado. Las fases se agregan con secuencia, fechas planificadas, porcentaje y estado. Los recursos y colaboradores se asignan desde el detalle del proyecto. Las auditorías registran hallazgos y cada plan de acción tiene responsable, vencimiento, evidencia y estado.

## Nómina y soportes

El salario base es mensual y el pago es quincenal. La liquidación usa el total devengado, deducciones y valor a recibir extraídos de los soportes importados; los aportes del trabajador se mantienen separados de los aportes a cargo de la empresa. La planilla de aportes se importa, visualiza y descarga como documento original. El PDF consolidado de volantes se recorta y distribuye por identificación; siempre se debe verificar la bandeja de pendientes antes de calcular.

## Respaldo operativo

Desde la carpeta del proyecto, con el entorno virtual activo:

```powershell
.\.venv\Scripts\python.exe -m flask --app wsgi:app backup-db --destination .\instance\backups
```

Conservar la base SQLite, `instance/payroll_documents` y `instance/backups` juntos. Probar la restauración sobre una copia, nunca sobre la base activa.

## Lista de cierre diario

1. Revisar novedades, incidentes y planes vencidos.
2. Confirmar asignaciones de proyectos, cuadrillas, vehículos y equipos.
3. Verificar volantes sin colaborador identificado.
4. Respaldar la base y documentos cuando se cierre un periodo de nómina.
