# TFU4 - Refugio de animales (UT4)

API REST que demuestra la aplicación de diferentes patrones de arquitectura:

### Disponibilidad
- **Health Endpoint Monitoring:** endpoints de health check para los servicios de la app (API, base de datos PosgreSQL, caché Redis).
- **Rate Limiting:** límite de 10 requests/min por IP.

### Rendimiento
- **Caché-Aside:** utiliza Redis para almacenar temporalmente los datos de los animales consultados (consulta muy frecuente).
- **Queue-Based Load Leveling:** las solicitudes de adopción se encolan en Redis mediante RQ y son procesadas de forma asíncrona por un administrador.

### Seguridad:
- **Federated Identity:** permite que los usuarios se autentiquen mediante Google OAuth, delegando la autenticación en un proveedor de identidad externo.
- **Valet Key:** genera un token temporal con permisos limitados para consultar una solicitud de adopción compartida.

### Facilidad de modificación y despliegue 
- **External Configuration Store:** centraliza la configuración de la aplicación mediante variables de entorno y archivos de configuración.

## Levantar la app

```bash
docker compose up --build --scale api=3
```

La API queda disponible en `http://localhost:8000` a través del balanceador (nginx).
Documentación interactiva: `http://localhost:8000/docs`.

## Correr la demo

Con la app levantada, en otra terminal:

```bash
./demo.sh
```

En Windows (PowerShell), usar la version equivalente:

```powershell
./demo.ps1
```

