# Alternativa sin runner: descarga de ONPE desde tu PC y publica en GitHub (usa tus credenciales de Git).
# Uso manual:  .\actualizar-local.ps1 [-Modo incremental|full|smoke]
param([ValidateSet("incremental","full","smoke")][string]$Modo = "incremental",
      [string]$Repo = "C:\erm",
      [switch]$Ventana, [switch]$Chrome, [int]$Hilos = 2, [int]$PausaMs = 500)
$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
Set-Location $Repo
git pull --rebase --autostash origin main
if (-not (Test-Path .venv)) { py -3 -m venv .venv; .\.venv\Scripts\python -m pip install -q -r requirements.txt; .\.venv\Scripts\python -m playwright install chromium }
$extra = @(); if ($Ventana) { $extra += "--headed" }; if ($Chrome) { $extra += "--chrome" }; $extra += @("--hilos", "$Hilos", "--pausa-ms", "$PausaMs")
$flag = switch ($Modo) { "full" { "--full" } "smoke" { "--smoke" } default { "" } }
if ($flag) { .\.venv\Scripts\python scraper\onpe_scraper.py --out data $flag @extra } else { .\.venv\Scripts\python scraper\onpe_scraper.py --out data @extra }
if ($LASTEXITCODE -ne 0) { Write-Host "Scraper termino con codigo $LASTEXITCODE (3=bloqueo ONPE, 2=control de calidad). No se publica nada."; exit $LASTEXITCODE }
git config --local user.name "dashboard-erm-bot"
git config --local user.email "actions@users.noreply.github.com"
git add data
git diff --cached --quiet
if ($LASTEXITCODE -eq 0) { Write-Host "Sin cambios"; exit 0 }
git commit -m ("datos: actualizacion ONPE " + (Get-Date).ToUniversalTime().ToString("yyyy-MM-dd HH:mm") + " UTC")
git push origin HEAD:main
