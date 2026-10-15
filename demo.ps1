# Script de demostración de la TFU3 (Parte 2) - version PowerShell (Windows)
# Requisito previo: docker compose up --build --scale api=3
$ErrorActionPreference = "Stop"
$BASE_URL = "http://localhost:8000"

Write-Host "=== 1) Componentes e interfaces + servicios sin estado ===" -ForegroundColor Cyan
Write-Host "Registramos un admin (componente Autenticacion, IAutenticacion):"
$timestamp = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$registroBody = '{\"email\":\"admin' + $timestamp + '@refugio.com\",\"password\":\"1234\",\"rol\":\"admin\"}'
$registroResp = curl.exe -s -X POST "$BASE_URL/auth/registro" -H "Content-Type: application/json" -d "$registroBody" | ConvertFrom-Json
$TOKEN = $registroResp.access_token
Write-Host "Token JWT obtenido (sin sesion en el servidor): $($TOKEN.Substring(0,20))..."
$AUTH = "Authorization: Bearer $TOKEN"

Write-Host ""
Write-Host "Creamos un animal (componente Animales, IAnimales):"
$animalBody = '{\"nombre\":\"Firulais\",\"especie\":\"perro\"}'
$animalResp = curl.exe -s -X POST "$BASE_URL/animales" -H "Content-Type: application/json" -H $AUTH -d "$animalBody" | ConvertFrom-Json
$animalResp | ConvertTo-Json
$ANIMAL_ID = $animalResp.id
Write-Host ""

Write-Host "Creamos un hogar transitorio (componente Hogares Transitorios, IHogares):"
$hogarBody = '{\"responsable\":\"JuanPerez\",\"direccion\":\"Calle123\"}'
curl.exe -s -X POST "$BASE_URL/hogares" -H "Content-Type: application/json" -H $AUTH -d "$hogarBody"
Write-Host ""

Write-Host ""
Write-Host "=== 2) Escalabilidad horizontal + servicios sin estado ===" -ForegroundColor Cyan
Write-Host "Pegamos 6 veces seguidas a /salud a traves del balanceador:"
Write-Host "distintas 'instancia' en la respuesta = distintas replicas atendiendo,"
Write-Host "cualquiera puede responder porque ninguna guarda estado local."
for ($i = 1; $i -le 6; $i++) {
    curl.exe -s "$BASE_URL/salud"
    Write-Host ""
}

Write-Host ""
Write-Host "=== 3) ACID (componente Adopciones) ===" -ForegroundColor Cyan
Write-Host "Creamos una solicitud de adopcion sobre el animal recien creado (id=$ANIMAL_ID):"
Write-Host "(reserva animal + asigna hogar en UNA transaccion)"
$solicitudBody = '{\"animal_id\":' + $ANIMAL_ID + ',\"interesado_email\":\"maria@mail.com\"}'
curl.exe -s -X POST "$BASE_URL/adopciones" -H "Content-Type: application/json" -H $AUTH -d "$solicitudBody"
Write-Host ""

Write-Host "Intentamos una segunda solicitud sobre el MISMO animal: debe fallar (409)"
Write-Host "porque la transaccion anterior ya lo dejo reservado -> no hay estado intermedio inconsistente."
$solicitudBody2 = '{\"animal_id\":' + $ANIMAL_ID + ',\"interesado_email\":\"otro@mail.com\"}'
curl.exe -s -o NUL -w "HTTP %{http_code}`n" -X POST "$BASE_URL/adopciones" -H "Content-Type: application/json" -H $AUTH -d "$solicitudBody2"

Write-Host ""
Write-Host "=== 4) Autenticacion / seguridad ===" -ForegroundColor Cyan
Write-Host "Pedimos /animales SIN token: debe rechazarse (401)."
curl.exe -s -o NUL -w "HTTP %{http_code}`n" "$BASE_URL/animales"

Write-Host ""
Write-Host "=== Fin de la demo ===" -ForegroundColor Green
