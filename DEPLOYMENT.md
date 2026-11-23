# Publicación del ERP

## Estado actual

El proyecto ya incluye `Dockerfile`, `docker-compose.yml` y `/healthz` para desplegarlo en un VPS o servicio cloud. El contenedor usa Waitress y conserva SQLite en un volumen persistente.

## Antes de hacerlo público

1. Definir `APP_ENV=production`.
2. Definir `SECRET_KEY` con una clave segura administrada fuera del repositorio. La aplicación no arranca en producción si falta o conserva el valor predeterminado.
3. Definir `TELEMETRY_API_KEY` si se reciben eventos de dispositivos.
4. Mantener `FLASK_DEBUG=0`; en producción el modo debug se fuerza a desactivado.
5. Mantener `SESSION_COOKIE_SECURE=1`; las cookies de sesión se fuerzan como Secure en producción y requieren HTTPS.
6. Elegir el proveedor cloud y crear un servidor con disco persistente.
7. Configurar un dominio y HTTPS mediante un proxy como Caddy o Nginx.
8. Restaurar una copia controlada de `instance/jardines.db` si se decide llevar los datos existentes.
9. Activar copias automáticas y probar restauración.
10. Para varios usuarios y crecimiento sostenido, migrar SQLite a PostgreSQL antes de escalar a varias réplicas.

## Arranque en un servidor con Docker

```bash
cp .env.example .env
# Editar .env con secretos de producción
docker compose up -d --build
curl http://127.0.0.1:5000/healthz
```

## Tiempo real

La API de telemetría ya recibe eventos reales con `X-API-Key`. La siguiente capa para operación cloud es publicar esos eventos mediante un broker/WebSocket compartido; no se habilita con una cola en memoria porque se perderían eventos al reiniciar o al usar más de una instancia.
