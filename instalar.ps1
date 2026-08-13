$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)
Write-Host "Instalando dependências do Projeto Doutrinador..." -ForegroundColor Cyan
python -m pip install -r requirements.txt
Write-Host "Instalação concluída." -ForegroundColor Green
