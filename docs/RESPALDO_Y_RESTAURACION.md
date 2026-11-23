# Respaldo y restauración operativa

## Qué debe respaldarse

- `instance/jardines.db`
- `instance/documents/`
- `instance/payroll_documents/`
- `instance/backups/`
- `.env`, conservado únicamente en un almacén seguro y nunca en un repositorio.

## Crear respaldo de la base

Desde la raíz oficial:

```powershell
.\.venv\Scripts\python.exe -m flask --app wsgi:app backup-db --destination .\instance\backups
```

El comando usa la API de backup de SQLite para obtener una copia consistente.

## Procedimiento recomendado

1. Crear el backup de la base.
2. Copiar `documents` y `payroll_documents` al mismo conjunto de respaldo.
3. Guardar el conjunto fuera del equipo principal.
4. Probar la restauración en una carpeta temporal, nunca sobre la base activa.
5. Verificar login, perfiles, documentos generados y nómina antes de declarar el backup válido.

## Pendiente para producción

La aplicación todavía requiere una política externa de cifrado de disco/archivos y una copia fuera del equipo. SQLite debe migrarse a PostgreSQL antes de escalar a múltiples instancias o alta concurrencia.
