$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:PYTHONPATH = Join-Path $projectRoot "src"
Set-Location $projectRoot
Write-Host "Iniciando o Projeto Doutrinador..." -ForegroundColor Cyan
Write-Host "Abra no navegador: http://192.168.10.105:8000" -ForegroundColor Yellow
python -m uvicorn doutrinador.presentation.api:app --host 192.168.10.105 --port 8000
