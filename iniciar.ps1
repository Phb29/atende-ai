# Liga o Atende.ai no seu PC (só você acessa: 127.0.0.1).
# Uso: clique com o botão direito neste arquivo > "Executar com o PowerShell".
# Para desligar: feche a janela ou aperte Ctrl+C.
#
# Escolha o provedor passando um parâmetro:
#   .\iniciar.ps1              -> Ollama (IA local, grátis)
#   .\iniciar.ps1 -Provedor regras     -> sem IA, só regras
#   .\iniciar.ps1 -Provedor anthropic  -> Claude (pede a chave na hora, não salva em arquivo)
param([ValidateSet("ollama", "regras", "anthropic")][string]$Provedor = "ollama")

$ErrorActionPreference = "Stop"
$raiz = $PSScriptRoot

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Instale o uv primeiro: https://docs.astral.sh/uv/" -ForegroundColor Red; exit 1
}

# Gera a tela na primeira vez (ou se a pasta sumiu).
if (-not (Test-Path "$raiz\backend\static\index.html")) {
    Write-Host "Gerando a tela (só na primeira vez)..." -ForegroundColor Cyan
    Push-Location "$raiz\frontend"
    npm ci --no-audit --no-fund; npm run build
    Pop-Location
    Copy-Item -Recurse "$raiz\frontend\dist" "$raiz\backend\static"
}

$env:ATENDE_PROVEDOR = $Provedor
if ($Provedor -eq "ollama") {
    $env:OLLAMA_MODELO = "qwen2.5:3b"
    $env:OLLAMA_NUM_GPU = "0"   # só processador: evita o erro de CUDA de algumas placas de vídeo
}
if ($Provedor -eq "anthropic" -and -not $env:ANTHROPIC_API_KEY) {
    $segura = Read-Host "Cole sua chave da API da Anthropic" -AsSecureString
    $env:ANTHROPIC_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($segura))
}

Set-Location "$raiz\backend"
Start-Process "http://127.0.0.1:8000"
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
