#!/usr/bin/env bash
# Script de demostración de la TFU3 (Parte 2).
# Requisito previo: docker compose up --build --scale api=3
set -e
BASE_URL="http://localhost:8000"

echo "=== 1) Componentes e interfaces + servicios sin estado ==="
echo "Registramos un admin (componente Autenticación, IAutenticacion):"
TIMESTAMP=$(date +%s)
TOKEN=$(curl -s -X POST "$BASE_URL/auth/registro" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"admin${TIMESTAMP}@refugio.com\",\"password\":\"1234\",\"rol\":\"admin\"}" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "Token JWT obtenido (sin sesión en el servidor): ${TOKEN:0:20}..."
AUTH="Authorization: Bearer $TOKEN"

echo
echo "Creamos un animal (componente Animales, IAnimales):"
ANIMAL_JSON=$(curl -s -X POST "$BASE_URL/animales" -H "Content-Type: application/json" -H "$AUTH" \
  -d '{"nombre":"Firulais","especie":"perro"}')
echo "$ANIMAL_JSON"
ANIMAL_ID=$(echo "$ANIMAL_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo
echo "Creamos un hogar transitorio (componente Hogares Transitorios, IHogares):"
curl -s -X POST "$BASE_URL/hogares" -H "Content-Type: application/json" -H "$AUTH" \
  -d '{"responsable":"Juan Pérez","direccion":"Calle 123"}'
echo

echo
echo "=== 2) Escalabilidad horizontal + servicios sin estado ==="
echo "Pegamos 6 veces seguidas a /salud a través del balanceador:"
echo "distintas 'instancia' en la respuesta = distintas réplicas atendiendo,"
echo "cualquiera puede responder porque ninguna guarda estado local."
for i in 1 2 3 4 5 6; do
  curl -s "$BASE_URL/salud"
  echo
done

echo
echo "=== 3) ACID (componente Adopciones) ==="
echo "Creamos una solicitud de adopción sobre el animal recién creado (id=$ANIMAL_ID):"
echo "(reserva animal + asigna hogar en UNA transacción)"
curl -s -X POST "$BASE_URL/adopciones" -H "Content-Type: application/json" -H "$AUTH" \
  -d "{\"animal_id\":$ANIMAL_ID,\"interesado_email\":\"maria@mail.com\"}"
echo
echo "Intentamos una segunda solicitud sobre el MISMO animal: debe fallar (409)"
echo "porque la transacción anterior ya lo dejó reservado -> no hay estado intermedio inconsistente."
curl -s -o /dev/null -w "HTTP %{http_code}\n" -X POST "$BASE_URL/adopciones" \
  -H "Content-Type: application/json" -H "$AUTH" \
  -d "{\"animal_id\":$ANIMAL_ID,\"interesado_email\":\"otro@mail.com\"}"

echo
echo "=== 4) Autenticación / seguridad ==="
echo "Pedimos /animales SIN token: debe rechazarse (401)."
curl -s -o /dev/null -w "HTTP %{http_code}\n" "$BASE_URL/animales"

echo
echo "=== Fin de la demo ==="
