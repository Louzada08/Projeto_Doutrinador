$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot
Write-Host "Instalando dependências do Projeto Doutrinador..." -ForegroundColor Cyan
$virtualEnvironment = Join-Path $projectRoot ".venv"
$pythonExecutable = Join-Path $virtualEnvironment "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonExecutable)) {
    python -m venv $virtualEnvironment
}
& $pythonExecutable -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Não foi possível instalar as dependências." }
Write-Host "Instalação concluída." -ForegroundColor Green
