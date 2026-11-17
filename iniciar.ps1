# Talent Match V6 — instalación y arranque en Windows PowerShell
# Uso:  .\iniciar.ps1            (primera vez: instala, crea .env, carga la demo y arranca)
#       .\iniciar.ps1 -SoloIniciar
param([switch]$SoloIniciar, [switch]$ReiniciarDemo)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv")) {
    Write-Host "Creando entorno virtual..." -ForegroundColor Cyan
    py -3 -m venv .venv
}
$py = ".\.venv\Scripts\python.exe"

if (-not $SoloIniciar) {
    Write-Host "Instalando dependencias de Python..." -ForegroundColor Cyan
    & $py -m pip install --upgrade pip | Out-Null
    & $py -m pip install -r requirements.txt
    & $py -m scripts.setup_env
    if (-not (Test-Path "data\talentmatch_v6.db") -or $ReiniciarDemo) {
        Write-Host "Cargando datos de demostración..." -ForegroundColor Cyan
        & $py -m scripts.seed_demo --reset
    }
}
Write-Host "Talent Match V6 en http://127.0.0.1:8000  (Ctrl+C para detener)" -ForegroundColor Green
& $py -m uvicorn app.main:app --host 127.0.0.1 --port 8000
