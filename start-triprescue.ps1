param([switch]$OpenBrowser)
$ErrorActionPreference = 'Stop'
$tripRoot = $PSScriptRoot
& (Join-Path $tripRoot 'start-local-ai.ps1')
$tripLogs = Join-Path $tripRoot '.artifacts\runtime'
New-Item -ItemType Directory -Path $tripLogs -Force | Out-Null

function Test-TripEndpoint([string]$Address) {
    try { $tripResponse = Invoke-WebRequest -Uri $Address -UseBasicParsing -TimeoutSec 3; return $tripResponse.StatusCode -eq 200 }
    catch { return $false }
}

if (-not (Test-TripEndpoint 'http://127.0.0.1:8000/api/health')) {
    $tripPython = Join-Path $tripRoot 'backend\.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $tripPython)) { throw 'Backend dependencies are missing. Follow README.md first.' }
    Start-Process -FilePath $tripPython -ArgumentList @('-m','uvicorn','app.main:app','--reload','--host','127.0.0.1','--port','8000') `
        -WorkingDirectory (Join-Path $tripRoot 'backend') -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $tripLogs 'backend.out.log') `
        -RedirectStandardError (Join-Path $tripLogs 'backend.err.log') | Out-Null
}

if (-not (Test-TripEndpoint 'http://127.0.0.1:5173/')) {
    $tripNode = Join-Path $tripRoot '.tools\node\node.exe'
    $tripVite = Join-Path $tripRoot 'frontend\node_modules\vite\bin\vite.js'
    if (-not (Test-Path -LiteralPath $tripNode) -or -not (Test-Path -LiteralPath $tripVite)) { throw 'Frontend dependencies are missing. Follow README.md first.' }
    Start-Process -FilePath $tripNode -ArgumentList @('node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5173','--strictPort') `
        -WorkingDirectory (Join-Path $tripRoot 'frontend') -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $tripLogs 'frontend.out.log') `
        -RedirectStandardError (Join-Path $tripLogs 'frontend.err.log') | Out-Null
}

for ($tripAttempt = 0; $tripAttempt -lt 30; $tripAttempt++) {
    if ((Test-TripEndpoint 'http://127.0.0.1:8000/api/health') -and (Test-TripEndpoint 'http://127.0.0.1:5173/api/health')) {
        Write-Output 'Wayva is ready at http://127.0.0.1:5173/'
        if ($OpenBrowser) { Start-Process 'http://127.0.0.1:5173/' }
        exit 0
    }
    Start-Sleep -Milliseconds 500
}
throw 'A server did not become ready. Check .artifacts\runtime logs.'
