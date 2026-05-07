param(
    [switch]$Force = $true,
    [string]$HfEndpoint = "https://hf-mirror.com",
    [string]$Proxy = "",
    [switch]$UpdateAgentContext
)

$ErrorActionPreference = "Stop"

Write-Host "==> Checking GitNexus"
gitnexus --version

Write-Host "==> Preparing GitNexus environment"
if ($Proxy) {
    $env:HTTP_PROXY = $Proxy
    $env:HTTPS_PROXY = $Proxy
    $env:ALL_PROXY = $Proxy
    Write-Host "Using proxy: $Proxy"
}
if ($HfEndpoint) {
    $env:HF_ENDPOINT = $HfEndpoint
}
if (-not $env:HF_HOME) {
    $env:HF_HOME = Join-Path $env:USERPROFILE ".cache\huggingface"
}
if (-not $env:GITNEXUS_EMBEDDING_DEVICE) {
    $env:GITNEXUS_EMBEDDING_DEVICE = "cpu"
}
if (-not $env:GITNEXUS_EMBEDDING_THREADS) {
    $env:GITNEXUS_EMBEDDING_THREADS = "2"
}

Write-Host "==> Running full GitNexus index"
New-Item -ItemType Directory -Force -Path "logs/gitnexus" | Out-Null

$forceArg = if ($Force) { "--force" } else { "" }
$agentArg = if ($UpdateAgentContext) { "" } else { "--skip-agents-md" }
gitnexus analyze $forceArg --embeddings --skills --verbose $agentArg 2>&1 |
    Tee-Object "logs/gitnexus/v1.4.7-full-index.log"

Write-Host "==> Checking status"
gitnexus status
gitnexus list

Write-Host "==> Done"
