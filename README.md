# TFU4 - Refugio de animales (UT4)

API REST que demuestra la aplicación de diferentes patrones de arquitectura:

Disponibilidad: 
- Health Endpoint Monitoring
- Rate Limiting

Rendimiento:
- Caché-Aside
- Queue-Based Load Leveling

Seguridad:
- Federated Identity
- Valet Key

Facilidad de modificación y despliegue: External Configuration Store

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

