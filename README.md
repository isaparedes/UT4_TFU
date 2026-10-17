# TFU4 - Refugio de animales (UT4)

API REST que demuestra la aplicación de diferentes patrones de arquitectura:

### Disponibilidad
- **Health Endpoint Monitoring:** endpoints de health check para los servicios de la app (API, base de datos PostgreSQL, caché Redis).
- **Rate Limiting:** límite de 10 requests/min por IP.

### Rendimiento
- **Caché-Aside:** utiliza Redis para almacenar temporalmente los datos de los animales consultados (consulta muy frecuente).
- **Queue-Based Load Leveling:** las solicitudes de adopción se encolan en Redis mediante RQ y son posteriormente consumidas por un worker.

### Seguridad:
- **Federated Identity:** permite que los usuarios se autentiquen mediante Google OAuth, delegando la autenticación en un proveedor de identidad externo.
- **Valet Key:** genera un token temporal con permisos limitados para consultar una solicitud de adopción compartida.

### Facilidad de modificación y despliegue 
- **External Configuration Store:** centraliza la configuración de la aplicación mediante variables de entorno y archivos de configuración.

## 1. Crear archivo .env en la raíz del proyecto con el siguiente contenido

```
JWT_SECRET=
SESSION_SECRET=

GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=

DATABASE_URL=

REDIS_URL=
REDIS_QUEUE_URL=

JOB_TIMEOUT=60
JOB_RESULT_TTL=86400
JOB_FAILURE_TTL=604800
CACHE_TTL_LISTA=30
CACHE_TTL_DETALLE=60

VALET_TTL=300
```

## 2. Levantar la app

```bash
docker compose up --build --scale api=3
```

La API queda disponible en `http://localhost:8000` a través del balanceador (nginx).
Documentación interactiva: `http://localhost:8000/docs`.

## 3. Correr la demo

Con la app levantada, en otra terminal:

```bash
./demo.sh
```

En Windows (PowerShell), usar la version equivalente:

```powershell
./demo.ps1
```
