#!/usr/bin/env bash
# Demo de los 7 patrones de arquitectura - Refugio de animales (TFU4)
# Requisitos: Docker Compose activo, curl, jq y la API publicada en localhost:8000.
# Ejecutar desde la carpeta del proyecto: bash demo.sh
set -Eeuo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
PASSWORD="Demo-1234!"
TIMESTAMP="$(date +%s)"
ADMIN_EMAIL="admin-demo-${TIMESTAMP}@refugio.com"
ADOPTER_EMAIL="adoptante-demo-${TIMESTAMP}@refugio.com"

command -v curl >/dev/null || { echo "Falta curl."; exit 1; }
command -v jq >/dev/null || { echo "Falta jq. Instala jq para poder leer las respuestas JSON."; exit 1; }
command -v docker >/dev/null || { echo "Falta Docker CLI."; exit 1; }

section() { printf '\n\033[1;36m=== %s ===\033[0m\n' "$1"; }
info() { printf '  %s\n' "$1"; }
fail() { echo "ERROR: $*" >&2; exit 1; }

request_json() {
  # Uso: request_json METHOD URL [TOKEN] [JSON_BODY]
  local method="$1" url="$2" token="${3:-}" body="${4:-}"
  local args=(-sS -X "$method" "$url" -H 'Content-Type: application/json')
  [[ -n "$token" ]] && args+=(-H "Authorization: Bearer $token")
  [[ -n "$body" ]] && args+=(-d "$body")
  curl "${args[@]}"
}

section "Preparación: crear cuentas de demo"
info "Registro de administrador de demo y adoptante. El registro público no permite elegir el rol."
request_json POST "$BASE_URL/auth/registro" "" "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$PASSWORD\"}" >/dev/null \
  || fail "No se pudo registrar el usuario administrador. ¿Está levantado Docker Compose?"
request_json POST "$BASE_URL/auth/registro" "" "{\"email\":\"$ADOPTER_EMAIL\",\"password\":\"$PASSWORD\"}" >/dev/null \
  || fail "No se pudo registrar el usuario adoptante."

info "Promoviendo la cuenta de demo a ADMIN en la base local."
docker compose exec -T api python -c "from app.database import SessionLocal; from app import models; db=SessionLocal(); email='$ADMIN_EMAIL'; u=db.query(models.Usuario).filter_by(email=email).first(); assert u is not None, 'No existe el usuario'; u.rol=models.Rol.ADMIN; db.commit(); db.close(); print('Rol ADMIN asignado')" \
  || fail "No se pudo asignar el rol ADMIN. Ejecutá el script desde la carpeta del docker-compose.yml."

login_admin="$(curl -sS -X POST "$BASE_URL/auth/login" -H 'Content-Type: application/x-www-form-urlencoded' --data-urlencode "username=$ADMIN_EMAIL" --data-urlencode "password=$PASSWORD")"
ADMIN_TOKEN="$(jq -r '.access_token // empty' <<<"$login_admin")"
[[ -n "$ADMIN_TOKEN" ]] || fail "No se pudo iniciar sesión con el administrador: $login_admin"
login_adopter="$(curl -sS -X POST "$BASE_URL/auth/login" -H 'Content-Type: application/x-www-form-urlencoded' --data-urlencode "username=$ADOPTER_EMAIL" --data-urlencode "password=$PASSWORD")"
ADOPTER_TOKEN="$(jq -r '.access_token // empty' <<<"$login_adopter")"
[[ -n "$ADOPTER_TOKEN" ]] || fail "No se pudo iniciar sesión con el adoptante: $login_adopter"
info "Cuentas listas. Admin: $ADMIN_EMAIL | Adoptante: $ADOPTER_EMAIL"

section "1. Disponibilidad: Health Endpoint Monitoring"
for endpoint in api-health db-health redis-health; do
  info "GET /$endpoint (con token admin):"
  curl -sS -w '\nHTTP %{http_code}\n' -H "Authorization: Bearer $ADMIN_TOKEN" "$BASE_URL/$endpoint"
done

section "2. Disponibilidad: Rate Limiting"
info "Enviando 40 solicitudes concurrentes al balanceador. Se cuentan los HTTP 429 (Too Many Requests)."
TMP_CODES="$(mktemp)"
for _ in $(seq 1 40); do
  (curl -sS -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $ADMIN_TOKEN" "$BASE_URL/api-health" >> "$TMP_CODES") &
done
wait
printf 'Respuestas HTTP 429: '
grep -c '^429$' "$TMP_CODES" || true
printf 'Distribución de códigos:\n'
sort "$TMP_CODES" | uniq -c
rm -f "$TMP_CODES"
info "Con Nginx configurado en 10r/m y burst=10, la cantidad de 429 depende de la concurrencia y del tráfico simultáneo."

# Dejar que se recupere el límite de solicitudes de Nginx.
sleep 20

section "3. Rendimiento: Cache-Aside"
info "Creando un animal disponible como admin para consultar su información."
ANIMAL_JSON="$(curl -sS -w $'\n%{http_code}' \
  -X POST "$BASE_URL/animales" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"nombre":"Cache Demo","especie":"perro"}')"

HTTP_STATUS="${ANIMAL_JSON##*$'\n'}"
ANIMAL_BODY="${ANIMAL_JSON%$'\n'*}"

if [[ "$HTTP_STATUS" != "201" && "$HTTP_STATUS" != "200" ]]; then
  echo "Error al crear el animal. HTTP $HTTP_STATUS"
  echo "Respuesta recibida:"
  echo "$ANIMAL_BODY"
  fail "No se pudo continuar con la demostración de Cache-Aside."
fi

ANIMAL_ID="$(jq -r '.id // empty' <<<"$ANIMAL_BODY")"
[[ -n "$ANIMAL_ID" ]] || fail "La respuesta no contiene el ID del animal: $ANIMAL_BODY"
echo "Animal creado correctamente. ID=$ANIMAL_ID"
info "Primera lectura GET /animales/$ANIMAL_ID:"
curl -sS -w '\nHTTP %{http_code}\n' -H "Authorization: Bearer $ADMIN_TOKEN" "$BASE_URL/animales/$ANIMAL_ID"
info "Segunda lectura del mismo recurso (debería poder servirse desde caché):"
curl -sS -w '\nHTTP %{http_code}\n' -H "Authorization: Bearer $ADMIN_TOKEN" "$BASE_URL/animales/$ANIMAL_ID"
info "Comprobando la clave animal:$ANIMAL_ID en Redis (DB 0):"
docker compose exec -T redis redis-cli -n 0 EXISTS "animal:$ANIMAL_ID"
info "El resultado 1 indica que la clave existe; TTL muestra los segundos restantes."
docker compose exec -T redis redis-cli -n 0 TTL "animal:$ANIMAL_ID"

# Dejar que se recupere el límite de solicitudes de Nginx.
sleep 20

section "4. Rendimiento: Queue-Based Load Leveling"
info "Registrando el hogar del adoptante y enviando una solicitud que se procesa en segundo plano."
HOGAR_JSON="$(request_json POST "$BASE_URL/hogares" "$ADOPTER_TOKEN" '{"responsable":"Adoptante Demo","direccion":"Calle Demo 123"}')"
info "Respuesta al registrar hogar: $HOGAR_JSON"
SOLICITUD_JSON="$(request_json POST "$BASE_URL/adopciones" "$ADOPTER_TOKEN" "{\"animal_id\":$ANIMAL_ID,\"tipo\":\"definitiva\"}")"
info "Respuesta inmediata de POST /adopciones (HTTP 202 y un identificador de trabajo): $SOLICITUD_JSON"
JOB_ID="$(jq -r '.job_id // .trabajo_id // empty' <<<"$SOLICITUD_JSON")"
if [[ -n "$JOB_ID" ]]; then
  for _ in $(seq 1 15); do
    JOB_JSON="$(curl -sS -H "Authorization: Bearer $ADOPTER_TOKEN" "$BASE_URL/adopciones/trabajos/$JOB_ID")"
    info "Estado del trabajo: $JOB_JSON"
    JOB_STATE="$(jq -r '.estado // .status // empty' <<<"$JOB_JSON")"

    # El worker devuelve el ID de la solicitud cuando termina.
    JOB_SOLICITUD_ID="$(jq -r '.solicitud_id // empty' <<<"$JOB_JSON")"

    if [[ "$JOB_STATE" == "failed" || "$JOB_STATE" == "fallido" ]]; then
      info "El trabajo terminó con error."
      break
    fi

    if [[ "$JOB_STATE" == "finished" ||
          "$JOB_STATE" == "completado" ||
          "$JOB_STATE" == "terminado" ]]; then
      break
    fi
    sleep 1
  done
else
  info "No se reconoció job_id/trabajo_id en la respuesta."
fi
# El ID lo devuelve el endpoint de estado del trabajo.
SOLICITUD_ID="${JOB_SOLICITUD_ID:-}"

if [[ -n "$SOLICITUD_ID" && "$SOLICITUD_ID" != "null" ]]; then
  info "Solicitud creada correctamente con ID=$SOLICITUD_ID."
else
  info "No se obtuvo solicitud_id del trabajo."
  info "Respuesta final del trabajo: ${JOB_JSON:-sin respuesta}"
fi
info "El endpoint devuelve el trabajo encolado; el worker consume la cola y persiste la solicitud de forma asíncrona."

# Dejar que se recupere el límite de solicitudes de Nginx.
sleep 10

section "5. Seguridad: Federated Identity (Google OAuth)"
info "Abrí esta URL en el navegador y completá el login con Google:"
echo "  $BASE_URL/auth/google/login"
info "La autenticación se delega en Google; el callback de la API emite el JWT de la aplicación."

# Dejar que se recupere el límite de solicitudes de Nginx.
sleep 20

section "6. Seguridad: Valet Key"
if [[ -n "${SOLICITUD_ID:-}" ]]; then
  info "Solicitando al admin una Valet Key de alcance limitado para la solicitud $SOLICITUD_ID."
  VALET_JSON="$(request_json POST "$BASE_URL/adopciones/$SOLICITUD_ID/valet-key" "$ADMIN_TOKEN")"
  echo "$VALET_JSON" | jq . 2>/dev/null || echo "$VALET_JSON"
  VALET_KEY="$(jq -r '.valet_key // .token // .access_token // empty' <<<"$VALET_JSON")"
  if [[ -n "$VALET_KEY" ]]; then
    info "Consultando la vista compartida usando la Valet Key (sin usar el JWT admin/adoptante):"
    curl -sS -w '\nHTTP %{http_code}\n' -H "Authorization: Bearer $VALET_KEY" "$BASE_URL/adopciones/compartida/$SOLICITUD_ID"
  else
    info "No se encontró el token en las propiedades valet_key/token/access_token. Revisá la respuesta anterior y ajustá el nombre del campo si tu endpoint usa otro."
  fi
else
  info "Se omite la Valet Key porque no se pudo obtener el ID de la solicitud."
fi

section "7. Facilidad de modificación/despliegue: External Configuration Store"
info "Leyendo valores no secretos cargados desde la configuración de la aplicación (Settings / variables de entorno):"
docker compose exec -T api python -c "from app.settings import settings; print('CACHE_TTL_LISTA =', settings.CACHE_TTL_LISTA); print('CACHE_TTL_DETALLE =', settings.CACHE_TTL_DETALLE); print('VALET_TTL =', settings.VALET_TTL); print('ACCESS_TOKEN_EXPIRE_MINUTES =', settings.ACCESS_TOKEN_EXPIRE_MINUTES); print('REDIS_URL =', settings.REDIS_URL)"
info "Demostración de cambio: modificá una de esas variables en .env (o en environment de Compose) y recreá el servicio API con: docker compose up -d --build --force-recreate api."

section "Fin de la demo"
echo "Usuarios de demo: $ADMIN_EMAIL y $ADOPTER_EMAIL"
echo "Contraseña de ambos: $PASSWORD"
echo "Nota: las cuentas y los datos creados quedan en la base hasta que los borres o reinicies el volumen."
