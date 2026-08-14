$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$certificate = Join-Path $projectRoot "data\certificates\doutrinador-ca.crt"
$httpsIp = if ($env:DOUTRINADOR_HTTPS_IP) { $env:DOUTRINADOR_HTTPS_IP } else { "192.168.10.105" }
$vpnIp = if ($env:DOUTRINADOR_VPN_IP) { $env:DOUTRINADOR_VPN_IP } else { "10.66.66.1" }

if (-not (Test-Path -LiteralPath $certificate)) {
    $pythonExecutable = Join-Path $projectRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $pythonExecutable)) {
        & (Join-Path $projectRoot "instalar.ps1")
    }
    $certificateDirectory = Join-Path $projectRoot "data\certificates"
    & $pythonExecutable scripts\generate_https_certificate.py `
        --ip $httpsIp `
        --ip $vpnIp `
        --output $certificateDirectory
    if ($LASTEXITCODE -ne 0) { throw "Não foi possível gerar o certificado HTTPS." }
}

Write-Host "Este script confiará na autoridade local do Doutrinador somente para o usuário atual." -ForegroundColor Yellow
$confirmation = Read-Host "Digite SIM para instalar o certificado"
if ($confirmation -cne "SIM") {
    Write-Host "Instalação cancelada."
    exit 0
}

Import-Certificate -FilePath $certificate -CertStoreLocation "Cert:\CurrentUser\Root" | Out-Null
Write-Host "Certificado instalado. Feche e reabra o navegador." -ForegroundColor Green
