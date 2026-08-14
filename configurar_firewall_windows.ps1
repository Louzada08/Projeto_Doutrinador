#Requires -RunAsAdministrator
$ErrorActionPreference = "Stop"
$port = if ($env:DOUTRINADOR_PORT) { $env:DOUTRINADOR_PORT } else { "8000" }
$vpnNetwork = if ($env:DOUTRINADOR_VPN_NETWORK) { $env:DOUTRINADOR_VPN_NETWORK } else { "10.66.66.0/24" }
$legacyRuleName = "Projeto Doutrinador HTTPS 8000"
$lanRuleName = "Projeto Doutrinador HTTPS $port - Rede Local"
$vpnRuleName = "Projeto Doutrinador HTTPS $port - VPN"

Write-Host "Esta operação permitirá conexões TCP de entrada na porta ${port}:" -ForegroundColor Yellow
Write-Host "- pela sub-rede local, somente no perfil Privado;" -ForegroundColor Yellow
Write-Host "- pela rede VPN $vpnNetwork, em qualquer perfil." -ForegroundColor Yellow
$confirmation = Read-Host "Digite SIM para criar as regras do Firewall"
if ($confirmation -cne "SIM") {
    Write-Host "Configuração cancelada."
    exit 0
}

foreach ($ruleName in @($legacyRuleName, $lanRuleName, $vpnRuleName)) {
    Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue |
        Remove-NetFirewallRule -ErrorAction SilentlyContinue
}

New-NetFirewallRule `
    -DisplayName $lanRuleName `
    -Direction Inbound `
    -Action Allow `
    -Protocol TCP `
    -LocalPort $port `
    -RemoteAddress LocalSubnet `
    -Profile Private | Out-Null

New-NetFirewallRule `
    -DisplayName $vpnRuleName `
    -Direction Inbound `
    -Action Allow `
    -Protocol TCP `
    -LocalPort $port `
    -RemoteAddress $vpnNetwork `
    -Profile Any | Out-Null

Write-Host "Porta $port liberada para a rede local e, de forma restrita, para $vpnNetwork." -ForegroundColor Green
