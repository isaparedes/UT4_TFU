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
JWT_SECRET=MySecretKeyJWT1234TFUANDISII!
SESSION_SECRET=TFU42026CarballidoMartonyParedes!

GOOGLE_CLIENT_ID=1056744787612-esper78stkm81lc6v25h2rpvl7mjhual.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=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
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

DATABASE_URL=postgresql+psycopg2://tfu4:tfu4@db:5432/tfu4

REDIS_URL=redis://redis:6379/0
REDIS_QUEUE_URL=redis://redis:6379/1

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

