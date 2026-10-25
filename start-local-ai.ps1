param(
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')]
    [string]$Model = 'qwen3:4b-q4_K_M',
    [switch]$DownloadModel
)

$ErrorActionPreference = 'Stop'
if ($Model -match '(?i)(:cloud|-cloud)$') { throw 'Select a local model, not a cloud model.' }
$tripRoot = $PSScriptRoot
$tripOllama = Join-Path $tripRoot '.tools\ollama\ollama.exe'
if (-not (Test-Path -LiteralPath $tripOllama)) {
    $tripInstalled = Get-Command ollama.exe -ErrorAction SilentlyContinue
    if (-not $tripInstalled) { throw 'Ollama is not installed. See the local AI setup section in README.md.' }
    $tripOllama = $tripInstalled.Source
}
$tripLogs = Join-Path $tripRoot '.artifacts\runtime'
New-Item -ItemType Directory -Path $tripLogs -Force | Out-Null
$tripModels = Join-Path $tripRoot '.tools\ollama-models'
New-Item -ItemType Directory -Path $tripModels -Force | Out-Null

function Get-TripLocalModels {
    try { return Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3 }
    catch { return $null }
}

$tripAvailable = Get-TripLocalModels
if (-not $tripAvailable) {
    $tripVariables = @{
        OLLAMA_HOST = '127.0.0.1:11434'
        OLLAMA_MODELS = $tripModels
        OLLAMA_NO_CLOUD = '1'
        OLLAMA_NUM_PARALLEL = '1'
        OLLAMA_MAX_LOADED_MODELS = '1'
    }
    $tripPrevious = @{}
    try {
        foreach ($tripName in $tripVariables.Keys) {
            $tripPrevious[$tripName] = [Environment]::GetEnvironmentVariable($tripName, 'Process')
            [Environment]::SetEnvironmentVariable($tripName, $tripVariables[$tripName], 'Process')
        }
        $tripProcess = Start-Process -FilePath $tripOllama -ArgumentList 'serve' -WindowStyle Hidden -PassThru `
            -WorkingDirectory $tripRoot `
            -RedirectStandardOutput (Join-Path $tripLogs 'ollama.out.log') `
            -RedirectStandardError (Join-Path $tripLogs 'ollama.err.log')
    } finally {
        foreach ($tripName in $tripPrevious.Keys) {
            [Environment]::SetEnvironmentVariable($tripName, $tripPrevious[$tripName], 'Process')
        }
    }
    for ($tripAttempt = 0; $tripAttempt -lt 30 -and -not $tripAvailable; $tripAttempt++) {
        Start-Sleep -Milliseconds 500
        $tripAvailable = Get-TripLocalModels
    }
    if (-not $tripAvailable) { throw 'Ollama did not start. Check .artifacts\runtime\ollama.err.log.' }
}

$tripHasModel = @($tripAvailable.models | Where-Object { $_.name -eq $Model -or $_.model -eq $Model }).Count -gt 0
if (-not $tripHasModel) {
    if (-not $DownloadModel) { throw "The local model is not downloaded. Run this script with -DownloadModel once (about 2.6 GB)." }
    Write-Output "Downloading $Model. This uses internet data but no paid AI API."
    $tripPreviousHost = [Environment]::GetEnvironmentVariable('OLLAMA_HOST', 'Process')
    try {
        $env:OLLAMA_HOST = '127.0.0.1:11434'
        $tripDownload = Start-Process -FilePath $tripOllama -ArgumentList @('pull', $Model) -WindowStyle Hidden -Wait -PassThru `
            -RedirectStandardOutput (Join-Path $tripLogs 'model-download.out.log') `
            -RedirectStandardError (Join-Path $tripLogs 'model-download.log')
        if ($tripDownload.ExitCode -ne 0) { throw 'The model download failed. Check .artifacts\runtime\model-download.log.' }
    } finally { [Environment]::SetEnvironmentVariable('OLLAMA_HOST', $tripPreviousHost, 'Process') }
    $tripAvailable = Get-TripLocalModels
    if (@($tripAvailable.models | Where-Object { $_.name -eq $Model -or $_.model -eq $Model }).Count -eq 0) {
        throw 'Ollama did not report the downloaded model.'
    }
}
Write-Output "Local AI ready: $Model at http://127.0.0.1:11434. No API key is needed."
