<#
.SYNOPSIS
    Levanta el sistema entero -API, worker y lectura- y dice dónde abrirlo.

.DESCRIPTION
    Hace lo que haya que hacer para que la página cargue a la primera: instala lo que
    falte, migra y siembra la base si está vacía, arranca las dos mitades y no imprime la
    URL hasta que las dos responden de verdad.

    Que espere a que respondan no es cosmético: uvicorn tarda unos segundos en abrir el
    puerto, y una URL impresa antes de tiempo lleva a un navegador que dice que no puede
    conectar, que es indistinguible de que algo esté roto.

    El worker es el que escribe: la API encola y él consume la cola. Sin él, el botón
    «Escribir la novela» responde que sí y no pasa nada más, que es el peor de los fallos
    posibles porque no se parece a un fallo.

    Ctrl+C para todo.

.PARAMETER PuertoApi
    Puerto de la API. Por defecto 8000, que es el que espera el proxy del frontend.

.PARAMETER PuertoLectura
    Puerto de la lectura. Por defecto 5173.

.PARAMETER Reiniciar
    Mata lo que esté ocupando esos puertos antes de arrancar. Sin esto, un servidor
    colgado de una sesión anterior produce WinError 10013, que no dice qué pasa.

.EXAMPLE
    .\run.ps1

.EXAMPLE
    .\run.ps1 -Reiniciar
#>

[CmdletBinding()]
param(
    [int]$PuertoApi = 8000,
    [int]$PuertoLectura = 5173,
    [switch]$Reiniciar
)

$ErrorActionPreference = "Stop"
$raiz = $PSScriptRoot
$procesos = @()

function Escribir($texto) { Write-Host "  $texto" }
function Paso($texto) { Write-Host "`n$texto" -ForegroundColor Cyan }

function Puerto-Ocupado([int]$puerto) {
    $null -ne (Get-NetTCPConnection -LocalPort $puerto -State Listen -ErrorAction SilentlyContinue)
}

function Liberar-Puerto([int]$puerto) {
    Get-NetTCPConnection -LocalPort $puerto -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 2
}

function Esperar-A([string]$url, [int]$segundos, [string]$que) {
    # Sondea hasta que responda. Devuelve $true o $false; no lanza.
    $limite = (Get-Date).AddSeconds($segundos)
    while ((Get-Date) -lt $limite) {
        try {
            Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3 | Out-Null
            return $true
        } catch {
            # Un 4xx o 5xx también significa que está escuchando: lo que se espera aquí
            # es que el puerto conteste, no que conteste bien.
            if ($_.Exception.Response) { return $true }
            Start-Sleep -Milliseconds 700
        }
    }
    Write-Host "  No respondió $que en $segundos s." -ForegroundColor Red
    return $false
}

try {
    Write-Host "MyStoryMaker" -ForegroundColor White
    Write-Host "============"

    # --- 0. Puertos ------------------------------------------------------------------
    foreach ($puerto in @($PuertoApi, $PuertoLectura)) {
        if (Puerto-Ocupado $puerto) {
            if ($Reiniciar) {
                Paso "Liberando el puerto $puerto"
                Liberar-Puerto $puerto
            } else {
                Write-Host "`nEl puerto $puerto ya está ocupado." -ForegroundColor Red
                Write-Host "  Si es una ejecución anterior que quedó colgada: .\run.ps1 -Reiniciar"
                exit 1
            }
        }
    }

    # --- 1. Dependencias --------------------------------------------------------------
    Paso "Dependencias"
    Push-Location $raiz
    uv sync --quiet
    Escribir "backend listo"
    if (-not (Test-Path (Join-Path $raiz "frontend\node_modules"))) {
        Escribir "instalando node_modules (la primera vez tarda)"
        Push-Location (Join-Path $raiz "frontend")
        npm install --no-audit --no-fund --silent
        Pop-Location
    }
    Escribir "frontend listo"
    Pop-Location

    # --- 2. Base de datos -------------------------------------------------------------
    Paso "Base de datos"
    Push-Location $raiz
    # Los dos comandos son idempotentes a proposito: `alembic upgrade head` no hace nada
    # si ya esta al dia, y la semilla se planta solo si el volumen no existe. Asi este
    # script se puede ejecutar mil veces sin preguntarse en que estado quedo la base.
    uv run alembic upgrade head 2>&1 | Out-Null
    Escribir "esquema al dia"
    $salidaSemilla = uv run python -m backend.store.semilla_demo 2>&1
    Escribir ($salidaSemilla | Select-Object -First 1)
    Pop-Location

    # --- 3. Arranque ------------------------------------------------------------------
    Paso "Arrancando"
    $api = Start-Process -FilePath "uv" `
        -ArgumentList "run", "uvicorn", "backend.api.main:app", "--port", "$PuertoApi" `
        -WorkingDirectory $raiz -PassThru -WindowStyle Hidden
    $procesos += $api

    $worker = Start-Process -FilePath "uv" `
        -ArgumentList "run", "python", "-m", "backend.worker" `
        -WorkingDirectory $raiz -PassThru -WindowStyle Hidden
    $procesos += $worker

    $lectura = Start-Process -FilePath "npm.cmd" `
        -ArgumentList "run", "dev", "--", "--port", "$PuertoLectura" `
        -WorkingDirectory (Join-Path $raiz "frontend") -PassThru -WindowStyle Hidden
    $procesos += $lectura

    $apiViva = Esperar-A "http://localhost:$PuertoApi/docs" 45 "la API"
    $lecturaViva = Esperar-A "http://localhost:$PuertoLectura/" 45 "la lectura"

    # El worker no escucha en ningún puerto, así que no se le puede sondear: lo que se
    # comprueba es que el proceso siga vivo unos segundos después de arrancar. Si su
    # arranque falla -por ejemplo, porque la base no está migrada- muere enseguida.
    Start-Sleep -Seconds 2
    $workerVivo = -not $worker.HasExited

    if (-not ($apiViva -and $lecturaViva -and $workerVivo)) {
        Write-Host "`nAlgo no arrancó. Prueba a mano para ver el error:" -ForegroundColor Red
        Write-Host "  uv run uvicorn backend.api.main:app --reload"
        Write-Host "  uv run python -m backend.worker"
        Write-Host "  cd frontend; npm run dev"
        exit 1
    }

    # --- 4. Listo ---------------------------------------------------------------------
    Write-Host ""
    Write-Host "  Abre:  " -NoNewline
    Write-Host "http://localhost:$PuertoLectura" -ForegroundColor Green
    Write-Host "  API:   http://localhost:$PuertoApi/docs"
    Write-Host "  Worker: en marcha, consumiendo la cola de tareas." -ForegroundColor DarkGray
    if (-not $env:ANTHROPIC_API_KEY) {
        Write-Host ""
        Write-Host "  Sin ANTHROPIC_API_KEY: «Escribir la novela» devolverá 503 diciendo qué falta." -ForegroundColor Yellow
        Write-Host "  Para ver el recorrido igualmente, usa «Escribir una muestra» (modo demostración)." -ForegroundColor Yellow
    }
    Write-Host ""
    Write-Host "  Ctrl+C para parar." -ForegroundColor DarkGray

    while ($true) { Start-Sleep -Seconds 1 }
}
finally {
    # Se ejecuta también con Ctrl+C: sin esto, los servidores quedan vivos y la próxima
    # ejecución choca contra sus puertos.
    if ($procesos.Count -gt 0) {
        Write-Host "`nParando..." -ForegroundColor DarkGray
        foreach ($p in $procesos) {
            if ($p -and -not $p.HasExited) {
                Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
            }
        }
        # npm lanza un hijo que no muere con su padre.
        Liberar-Puerto $PuertoLectura
        Liberar-Puerto $PuertoApi
    }
}
