
# Demo de los 7 patrones de arquitectura - Refugio de animales (TFU4)
# Ejecutar desde PowerShell en la carpeta del docker-compose.yml:
# .\demo.ps1

$ErrorActionPreference = "Stop"

$BASE_URL = if ($env:BASE_URL) { $env:BASE_URL } else { "http://localhost:8000" }
$PASSWORD = "Demo-1234!"
$TIMESTAMP = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$ADMIN_EMAIL = "admin-demo-$TIMESTAMP@refugio.com"
$ADOPTER_EMAIL = "adoptante-demo-$TIMESTAMP@refugio.com"
$MAX_RETRIES = 10

if (-not (Get-Command curl.exe -ErrorAction SilentlyContinue)) {
    throw "No se encontró curl.exe. Comprobá que curl esté instalado."
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "No se encontró Docker CLI."
}
if (-not (Get-Command jq -ErrorAction SilentlyContinue)) {
    Write-Host "Aviso: jq no está instalado. Este script usa ConvertFrom-Json de PowerShell."
}

function Section([string]$Title) {
    Write-Host "`n=== $Title ===" -ForegroundColor Cyan
}

function Info([string]$Message) {
    Write-Host "  $Message"
}

function Fail([string]$Message) {
    throw $Message
}


function Invoke-Api {
    param(
        [Parameter(Mandatory)][string]$Method,
        [Parameter(Mandatory)][string]$Url,
        [string]$Token = "",
        [string]$Body = "",
        [string]$ContentType = "application/json"
    )

    $tempBodyFile = $null

    try {
        for ($attempt = 1; $attempt -le $MAX_RETRIES; $attempt++) {
            $curlArgs = @(
                "-sS",
                "--connect-timeout", "5",
                "--max-time", "30",
                "-X", $Method,
                $Url,
                "-H", "Content-Type: $ContentType",
                "-w", "`n%{http_code}"
            )

            if ($Token) {
                $curlArgs += @("-H", "Authorization: Bearer $Token")
            }

            if ($Body -ne "") {
                # Guardar el JSON en UTF-8 sin BOM.
                $tempBodyFile = [System.IO.Path]::GetTempFileName()
                $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
                [System.IO.File]::WriteAllText(
                    $tempBodyFile,
                    $Body,
                    $utf8NoBom
                )

                $curlArgs += @("--data-binary", "@$tempBodyFile")
            }

            $response = (& curl.exe @curlArgs | Out-String).TrimEnd()

            if ($LASTEXITCODE -ne 0 -and -not $response) {
                $status = "000"
                $responseBody = ""
            }
            else {
                $lastNewline = $response.LastIndexOf("`n")

                if ($lastNewline -lt 0) {
                    $status = "000"
                    $responseBody = $response
                }
                else {
                    $status = $response.Substring($lastNewline + 1).Trim()
                    $responseBody = $response.Substring(0, $lastNewline)
                }
            }

            if ($status -match '^2\d\d$') {
                return [PSCustomObject]@{
                    StatusCode = [int]$status
                    Body       = $responseBody
                }
            }

            if ($status -in @("429", "502", "503", "504", "000")) {
                Info "HTTP $status en $Url. Intento $attempt/$MAX_RETRIES."
                Start-Sleep -Seconds 2
                continue
            }

            throw "HTTP $status en $Url. Respuesta: $responseBody"
        }

        throw "Se agotaron los reintentos para $Url."
    }
    finally {
        if ($tempBodyFile -and (Test-Path $tempBodyFile)) {
            Remove-Item $tempBodyFile -Force
        }
    }
}


function Convert-ResponseJson {
    param(
        [Parameter(Mandatory)][string]$Body,
        [Parameter(Mandatory)][string]$Description
    )

    try {
        return ($Body | ConvertFrom-Json -ErrorAction Stop)
    }
    catch {
        throw "$Description no devolvió JSON válido. Respuesta recibida: $Body"
    }
}

function Login-Demo {
    param([string]$Email)

    for ($attempt = 1; $attempt -le $MAX_RETRIES; $attempt++) {
        $curlArgs = @(
            "-sS",
            "--connect-timeout", "5",
            "--max-time", "30",
            "-X", "POST",
            "$BASE_URL/auth/login",
            "-H", "Content-Type: application/x-www-form-urlencoded",
            "--data-urlencode", "username=$Email",
            "--data-urlencode", "password=$PASSWORD",
            "-w", "`n%{http_code}"
        )

        $response = (& curl.exe @curlArgs | Out-String).TrimEnd()
        $lastNewline = $response.LastIndexOf("`n")

        if ($lastNewline -ge 0) {
            $status = $response.Substring($lastNewline + 1).Trim()
            $body = $response.Substring(0, $lastNewline)
        }
        else {
            $status = "000"
            $body = $response
        }

        if ($status -match '^2\d\d$') {
            $login = Convert-ResponseJson $body "Login de $Email"
            if (-not $login.access_token) {
                throw "El login de $Email no devolvió access_token. Respuesta: $body"
            }
            return [string]$login.access_token
        }

        if ($status -in @("429", "502", "503", "504", "000")) {
            Info "Login temporalmente limitado. Intento $attempt/$MAX_RETRIES."
            Start-Sleep -Seconds 2
            continue
        }

        throw "Error de login HTTP $status para $Email. Respuesta: $body"
    }

    throw "No se pudo iniciar sesión con $Email después de varios intentos."
}

# ------------------------------------------------------------
# Preparación: crear las cuentas de demostración
# ------------------------------------------------------------

Section "Preparación: crear cuentas de demo"

Info "Registrando administrador y adoptante. El registro público no permite elegir el rol."

$adminBody = @{
    email    = $ADMIN_EMAIL
    password = $PASSWORD
} | ConvertTo-Json -Compress

$adopterBody = @{
    email    = $ADOPTER_EMAIL
    password = $PASSWORD
} | ConvertTo-Json -Compress

$null = Invoke-Api -Method POST -Url "$BASE_URL/auth/registro" -Body $adminBody
$null = Invoke-Api -Method POST -Url "$BASE_URL/auth/registro" -Body $adopterBody

Info "Asignando ADMIN al usuario de demo en la base local."

$pythonCommand = "from app.database import SessionLocal; from app import models; db=SessionLocal(); u=db.query(models.Usuario).filter_by(email='$ADMIN_EMAIL').first(); assert u is not None, 'No existe el usuario'; u.rol=models.Rol.ADMIN; db.commit(); db.close(); print('Rol ADMIN asignado')"

& docker compose exec -T api python -c $pythonCommand
if ($LASTEXITCODE -ne 0) {
    throw "No se pudo asignar el rol ADMIN. Ejecutá el script desde la carpeta del proyecto."
}

Start-Sleep -Seconds 2

$ADMIN_TOKEN = Login-Demo $ADMIN_EMAIL
$ADOPTER_TOKEN = Login-Demo $ADOPTER_EMAIL

Info "Cuentas listas."
Info "Admin: $ADMIN_EMAIL"
Info "Adoptante: $ADOPTER_EMAIL"

# ------------------------------------------------------------
# 1. Health Endpoint Monitoring
# ------------------------------------------------------------

Section "1. Disponibilidad: Health Endpoint Monitoring"

foreach ($endpoint in @("api-health", "db-health", "redis-health")) {
    Info "GET /$endpoint"

    try {
        $result = Invoke-Api -Method GET -Url "$BASE_URL/$endpoint" -Token $ADMIN_TOKEN
        Write-Host $result.Body
        Write-Host "HTTP $($result.StatusCode)"
    }
    catch {
        Info "No se pudo consultar /$endpoint : $($_.Exception.Message)"
    }
}

Info "Los endpoints están protegidos como ADMIN. Los monitores internos deben contemplar la autenticación."

# ------------------------------------------------------------
# 2. Rate Limiting
# ------------------------------------------------------------

Section "2. Disponibilidad: Rate Limiting"

Info "Enviando 40 solicitudes concurrentes a /api-health."
Info "Esta prueba puede producir HTTP 429; después se espera para que se recupere el límite."

$rateLimitJobs = @()

for ($i = 1; $i -le 40; $i++) {
    $rateLimitJobs += Start-Job -ArgumentList $BASE_URL, $ADMIN_TOKEN -ScriptBlock {
        param($url, $token)

        $result = & curl.exe -sS --connect-timeout 5 --max-time 20 `
            -o NUL -w "%{http_code}" `
            -H "Authorization: Bearer $token" `
            "$url/api-health" 2>$null

        if ($LASTEXITCODE -ne 0) {
            "000"
        }
        else {
            "$result".Trim()
        }
    }
}

Wait-Job -Job $rateLimitJobs | Out-Null

$codes = @(
    foreach ($job in $rateLimitJobs) {
        Receive-Job -Job $job
    }
)

Remove-Job -Job $rateLimitJobs -Force

$count429 = @($codes | Where-Object { "$_".Trim() -eq "429" }).Count
Write-Host "Respuestas HTTP 429: $count429"
Write-Host "Distribución de códigos:"

$codes |
    Group-Object |
    Sort-Object Name |
    ForEach-Object {
        Write-Host ("  {0}: {1}" -f $_.Name, $_.Count)
    }

Info "Con rate=10r/s y burst=10, la distribución depende de la configuración de Nginx y de la concurrencia."

Info "Esperando 10 segundos para que se recupere el límite..."
Start-Sleep -Seconds 10

# ------------------------------------------------------------
# 3. Cache-Aside
# ------------------------------------------------------------

Section "3. Rendimiento: Cache-Aside"

Info "Creando un animal disponible."

$animalBody = @{
    nombre  = "Cache Demo"
    especie = "perro"
} | ConvertTo-Json -Compress

$animalResponse = Invoke-Api -Method POST -Url "$BASE_URL/animales" `
    -Token $ADMIN_TOKEN -Body $animalBody

$animal = Convert-ResponseJson $animalResponse.Body "Creación del animal"
$ANIMAL_ID = $animal.id

if ($null -eq $ANIMAL_ID) {
    throw "La respuesta no contiene el ID del animal: $($animalResponse.Body)"
}

Info "Animal creado correctamente. ID=$ANIMAL_ID"

Info "Primera lectura del detalle:"
$detail1 = Invoke-Api -Method GET -Url "$BASE_URL/animales/$ANIMAL_ID" -Token $ADMIN_TOKEN
Write-Host $detail1.Body
Write-Host "HTTP $($detail1.StatusCode)"

Info "Segunda lectura del mismo detalle:"
$detail2 = Invoke-Api -Method GET -Url "$BASE_URL/animales/$ANIMAL_ID" -Token $ADMIN_TOKEN
Write-Host $detail2.Body
Write-Host "HTTP $($detail2.StatusCode)"

Info "Comprobando la clave animal:$ANIMAL_ID en Redis."
& docker compose exec -T redis redis-cli -n 0 EXISTS "animal:$ANIMAL_ID"
if ($LASTEXITCODE -ne 0) {
    Info "No se pudo consultar Redis."
}

Info "TTL de la clave:"
& docker compose exec -T redis redis-cli -n 0 TTL "animal:$ANIMAL_ID"
if ($LASTEXITCODE -ne 0) {
    Info "No se pudo consultar el TTL."
}

Info "Esperando 20 segundos..."
Start-Sleep -Seconds 20

# ------------------------------------------------------------
# 4. Queue-Based Load Leveling
# ------------------------------------------------------------

Section "4. Rendimiento: Queue-Based Load Leveling"

Info "Registrando el hogar del adoptante."

$homeBody = @{
    responsable = "Adoptante Demo"
    direccion   = "Calle Demo 123"
} | ConvertTo-Json -Compress

$homeResponse = Invoke-Api -Method POST -Url "$BASE_URL/hogares" `
    -Token $ADOPTER_TOKEN -Body $homeBody

Info "Respuesta del hogar: $($homeResponse.Body)"

Info "Enviando una solicitud de adopción a la cola."

$adoptionBody = @{
    animal_id = [int]$ANIMAL_ID
    tipo      = "definitiva"
} | ConvertTo-Json -Compress

$adoptionResponse = Invoke-Api -Method POST -Url "$BASE_URL/adopciones" `
    -Token $ADOPTER_TOKEN -Body $adoptionBody

Info "Respuesta inmediata: $($adoptionResponse.Body)"

$adoption = Convert-ResponseJson $adoptionResponse.Body "Creación de la solicitud"
$JOB_ID = $adoption.job_id

if (-not $JOB_ID) {
    $JOB_ID = $adoption.trabajo_id
}

$SOLICITUD_ID = $null
$JOB_JSON = ""

if ($JOB_ID) {
    Info "ID del trabajo: $JOB_ID"

    for ($i = 1; $i -le 15; $i++) {
        try {
            $jobResponse = Invoke-Api -Method GET `
                -Url "$BASE_URL/adopciones/trabajos/$JOB_ID" `
                -Token $ADOPTER_TOKEN

            $JOB_JSON = $jobResponse.Body
            $jobData = Convert-ResponseJson $JOB_JSON "Estado del trabajo"

            Info "Estado del trabajo: $JOB_JSON"

            if ($jobData.solicitud_id) {
                $SOLICITUD_ID = $jobData.solicitud_id
            }

            if ($jobData.estado -in @("failed", "fallido")) {
                Info "El trabajo terminó con error."
                break
            }

            if ($jobData.estado -in @("finished", "completado", "terminado")) {
                break
            }
        }
        catch {
            Info "No se pudo consultar el estado del trabajo: $($_.Exception.Message)"
            break
        }

        Start-Sleep -Seconds 1
    }
}
else {
    Info "La respuesta no contiene job_id ni trabajo_id."
}

if ($SOLICITUD_ID) {
    Info "Solicitud creada correctamente con ID=$SOLICITUD_ID."
}
else {
    Info "No se obtuvo solicitud_id del trabajo."
    Info "Última respuesta: $JOB_JSON"
}

Info "Esperando 20 segundos..."
Start-Sleep -Seconds 20

# ------------------------------------------------------------
# 5. Federated Identity
# ------------------------------------------------------------

Section "5. Seguridad: Federated Identity (Google OAuth)"

$googleUrl = "$BASE_URL/auth/google/login"

Info "Se abrirá el navegador para iniciar el flujo de autenticación con Google."
Info "Completá el inicio de sesión y comprobá que la API procese el callback."

try {
    Start-Process $googleUrl
    Info "Navegador abierto: $googleUrl"
}
catch {
    Info "No se pudo abrir el navegador automáticamente."
    Info "Abrí manualmente: $googleUrl"
}

Info "La demostración depende de que las credenciales y el callback de Google estén configurados."
Info "Esperando 10 segundos antes de continuar..."
Start-Sleep -Seconds 10

# ------------------------------------------------------------
# 6. Valet Key
# ------------------------------------------------------------

Section "6. Seguridad: Valet Key"

if ($SOLICITUD_ID) {
    Info "Solicitando una Valet Key para la solicitud $SOLICITUD_ID."

    try {
        $valetResponse = Invoke-Api -Method POST `
            -Url "$BASE_URL/adopciones/$SOLICITUD_ID/valet-key" `
            -Token $ADMIN_TOKEN

        $valet = Convert-ResponseJson $valetResponse.Body "Generación de Valet Key"
        Write-Host ($valet | ConvertTo-Json -Depth 10)

        $VALET_KEY = $valet.valet_key
        if (-not $VALET_KEY) { $VALET_KEY = $valet.token }
        if (-not $VALET_KEY) { $VALET_KEY = $valet.access_token }

        if ($VALET_KEY) {
            Info "Consultando la vista compartida utilizando la Valet Key."

            $sharedResponse = Invoke-Api -Method GET `
                -Url "$BASE_URL/adopciones/compartida/$SOLICITUD_ID" `
                -Token $VALET_KEY

            Write-Host $sharedResponse.Body
            Write-Host "HTTP $($sharedResponse.StatusCode)"
        }
        else {
            Info "La respuesta no contiene valet_key, token ni access_token."
        }
    }
    catch {
        Info "No se pudo completar la demostración de Valet Key: $($_.Exception.Message)"
    }
}
else {
    Info "Se omite la Valet Key porque no se obtuvo el ID de la solicitud."
}

Info "Esperando 10 segundos..."
Start-Sleep -Seconds 10

# ------------------------------------------------------------
# 7. External Configuration Store
# ------------------------------------------------------------

Section "7. Facilidad de modificación/despliegue: External Configuration Store"

Info "Leyendo valores de configuración no secretos desde app.settings."

$configCommand = @'
from app.settings import settings
print("CACHE_TTL_LISTA =", settings.CACHE_TTL_LISTA)
print("CACHE_TTL_DETALLE =", settings.CACHE_TTL_DETALLE)
print("VALET_TTL =", settings.VALET_TTL)
print("ACCESS_TOKEN_EXPIRE_MINUTES =", settings.ACCESS_TOKEN_EXPIRE_MINUTES)
print("REDIS_URL =", settings.REDIS_URL)
'@

$configCommand | & docker compose exec -T api python -c "import sys; exec(sys.stdin.read())"

if ($LASTEXITCODE -ne 0) {
    Info "No se pudo leer la configuración. Revisá el servicio API y los nombres de los atributos."
}

Info "Para demostrar un cambio, modificá una variable en .env o en environment de Compose."
Info "Después recreá la API con:"
Write-Host "  docker compose up -d --build --force-recreate api"
Info "No imprimas JWT_SECRET ni GOOGLE_CLIENT_SECRET."

# ------------------------------------------------------------
# Fin
# ------------------------------------------------------------

Section "Fin de la demo"

Write-Host "Usuario administrador: $ADMIN_EMAIL"
Write-Host "Usuario adoptante: $ADOPTER_EMAIL"
Write-Host "Contraseña de ambos: $PASSWORD"
Write-Host "Las cuentas y los datos creados permanecen en la base de datos."
