# Instala el runner propio de GitHub Actions en Windows (se ejecuta UNA vez, en PowerShell).
# Uso:  .\instalar-runner.ps1 -Token <TOKEN_DE_REGISTRO>
# El token se obtiene en: repo > Settings > Actions > Runners > New self-hosted runner (caduca en 1 h).
param([Parameter(Mandatory=$true)][string]$Token,
      [string]$Repo = "https://github.com/cmucching/dashboard-erm-2026",
      [string]$Dir = "C:\actions-runner")
$ErrorActionPreference = "Stop"
$rel = Invoke-RestMethod "https://api.github.com/repos/actions/runner/releases/latest"
$asset = $rel.assets | Where-Object { $_.name -like "actions-runner-win-x64-*.zip" } | Select-Object -First 1
New-Item -ItemType Directory -Force $Dir | Out-Null
Set-Location $Dir
Invoke-WebRequest $asset.browser_download_url -OutFile runner.zip
Expand-Archive runner.zip -DestinationPath . -Force
.\config.cmd --url $Repo --token $Token --labels "windows,onpe" --unattended --replace
# Ejecutar como servicio (arranca con Windows). Requiere PowerShell como administrador.
.\svc.cmd install
.\svc.cmd start
Write-Host "Runner instalado. Verifica en GitHub: Settings > Actions > Runners (debe decir Idle)."
