$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:PYTHONPATH = Join-Path $projectRoot "src"
$httpsIp = if ($env:DOUTRINADOR_HTTPS_IP) { $env:DOUTRINADOR_HTTPS_IP } else { "192.168.10.105" }
$vpnIp = if ($env:DOUTRINADOR_VPN_IP) { $env:DOUTRINADOR_VPN_IP } else { "10.66.66.1" }
$httpsPort = if ($env:DOUTRINADOR_PORT) { $env:DOUTRINADOR_PORT } else { "8000" }
$certificateDirectory = Join-Path $projectRoot "data\certificates"
$certificate = Join-Path $certificateDirectory "doutrinador-server.crt"
$privateKey = Join-Path $certificateDirectory "doutrinador-server.key"
$pythonExecutable = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonExecutable)) {
    Write-Host "Preparando o ambiente na primeira execução..." -ForegroundColor Cyan
    & (Join-Path $projectRoot "instalar.ps1")
}

Set-Location $projectRoot
& $pythonExecutable scripts\generate_https_certificate.py `
    --ip $httpsIp `
    --ip $vpnIp `
    --output $certificateDirectory
if ($LASTEXITCODE -ne 0) { throw "Não foi possível gerar o certificado HTTPS." }

Write-Host "Iniciando o Projeto Doutrinador com HTTPS..." -ForegroundColor Cyan
Write-Host "Na rede local: https://${httpsIp}:${httpsPort}" -ForegroundColor Yellow
Write-Host "Pela VPN WireGuard: https://${vpnIp}:${httpsPort}" -ForegroundColor Yellow
Write-Host "Instale data\certificates\doutrinador-ca.crt nos dispositivos clientes." -ForegroundColor Yellow
& $pythonExecutable -m uvicorn doutrinador.presentation.api:app `
    --host 0.0.0.0 `
    --port $httpsPort `
    --ssl-certfile $certificate `
    --ssl-keyfile $privateKey
