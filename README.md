# TFU4 - Refugio de animales (UT4)

API REST que demuestra: componentes e interfaces, escalabilidad horizontal,
contenedores (Docker), transacciones ACID y servicios sin estado.

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

## Estructura

- `app/auth.py` — componente Autenticación (JWT, sin estado)
- `app/animales.py` — componente Animales
- `app/hogares.py` — componente Hogares Transitorios
- `app/adopciones.py` — componente Adopciones (orquesta a los dos anteriores
  dentro de una transacción ACID sobre PostgreSQL)
- `docker-compose.yaml` — Postgres + API (escalable) + balanceador nginx
