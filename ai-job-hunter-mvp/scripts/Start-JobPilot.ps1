param(
  [int]$BackendPort = 8000,
  [int]$FrontendPort = 3000,
  [string]$DataDirectory = "",
  [switch]$OpenBrowser,
  [switch]$Install
)
$ErrorActionPreference = 'Stop'
$workspaceDir = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$backendDir = Join-Path $workspaceDir 'backend'
$frontendDir = Join-Path $workspaceDir 'frontend'
if (!$DataDirectory) {
  $DataDirectory = if ($env:JOBPILOT_DATA_DIR) { $env:JOBPILOT_DATA_DIR } else { Join-Path $env:LOCALAPPDATA 'JobPilotAI' }
}
$runtimeDir = [IO.Path]::GetFullPath($DataDirectory)
$repositoryDir = $workspaceDir
$probeDir = $workspaceDir
while ($probeDir) {
  if (Test-Path -LiteralPath (Join-Path $probeDir '.git')) { $repositoryDir = $probeDir; break }
  $probeDir = Split-Path -Parent $probeDir
}
if ($runtimeDir.Equals($repositoryDir,[StringComparison]::OrdinalIgnoreCase) -or $runtimeDir.StartsWith($repositoryDir + '\',[StringComparison]::OrdinalIgnoreCase)) {
  throw 'Choose an application-data directory outside the source repository.'
}
if ($BackendPort -lt 1024 -or $BackendPort -gt 65535 -or $FrontendPort -lt 1024 -or $FrontendPort -gt 65535 -or $BackendPort -eq $FrontendPort) { throw 'Choose two different local ports between 1024 and 65535.' }
New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
$logsDir = Join-Path $runtimeDir 'logs'
New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
$statePath = Join-Path $runtimeDir 'launcher.json'
$pythonExe = Join-Path $backendDir '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $pythonExe)) {
  Push-Location $backendDir
  try { python -m venv .venv; if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.11+ and retry.' } } finally { Pop-Location }
  $Install = $true
}
& $pythonExe -c "import fastapi,uvicorn,sqlalchemy,alembic,docx,reportlab,cryptography" 2>$null
if ($LASTEXITCODE -ne 0) { $Install = $true }
if ($Install) {
  & $pythonExe -m pip install -r (Join-Path $backendDir 'requirements.txt')
  if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
}
if (!(Get-Command node -ErrorAction SilentlyContinue) -or !(Get-Command npm -ErrorAction SilentlyContinue)) { throw 'Install Node.js 22+ and npm, then retry.' }
if (!(Test-Path -LiteralPath (Join-Path $frontendDir 'node_modules\next\dist\bin\next'))) {
  Push-Location $frontendDir
  try { npm install; if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' } } finally { Pop-Location }
}

function Read-LocalJson([string]$Url) {
  try { return Invoke-RestMethod -Uri $Url -TimeoutSec 3 } catch { return $null }
}
function Port-InUse([int]$Port) {
  $client = New-Object Net.Sockets.TcpClient
  try { $client.Connect('127.0.0.1',$Port); return $true } catch { return $false } finally { $client.Dispose() }
}

$backendUrl = "http://127.0.0.1:$BackendPort"
$frontendUrl = "http://127.0.0.1:$FrontendPort"
$env:JOBPILOT_DATA_DIR = $runtimeDir
$env:JOBPILOT_ENABLE_DEMO = '0'
$env:NEXT_PUBLIC_ENABLE_DEMO = 'false'
$env:NEXT_PUBLIC_LEGACY_WORKSPACE = 'false'
$env:FRONTEND_ORIGIN = $frontendUrl
$env:BACKEND_API_URL = $backendUrl
$env:JOBPILOT_DIST_DIR = '.next-local'
$env:NEXT_TELEMETRY_DISABLED = '1'
Push-Location $backendDir
try { $expectedInstance = & $pythonExe -c "import hashlib; from app.db import data_directory; print(hashlib.sha256(str(data_directory()).casefold().encode()).hexdigest()[:16])"; if ($LASTEXITCODE -ne 0) { throw 'Could not resolve the local data directory.' } } finally { Pop-Location }
$state = @{workspace=$workspaceDir;backend=$null;frontend=$null;backend_port=$BackendPort;frontend_port=$FrontendPort;created_at=(Get-Date).ToUniversalTime().ToString('o')}
if (Test-Path -LiteralPath $statePath) {
  try {
    $previous = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    if ($previous.workspace -eq $workspaceDir) { $state.backend=$previous.backend; $state.frontend=$previous.frontend }
  } catch { }
}
$health = Read-LocalJson "$backendUrl/health"
if (!$health -or $health.schema_version -ne '0003_queue_integrity' -or $health.instance_id -ne $expectedInstance) {
  if (Port-InUse $BackendPort) { throw "Port $BackendPort is occupied by another or older backend. Choose another port or stop that instance yourself." }
  $process = Start-Process -FilePath $pythonExe -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port',"$BackendPort") -WorkingDirectory $backendDir -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logsDir 'backend.log') -RedirectStandardError (Join-Path $logsDir 'backend-error.log')
  $state.backend = @{pid=$process.Id;started=$process.StartTime.ToUniversalTime().ToString('o')}
  $state | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $statePath -Encoding UTF8
  for ($attempt=0; $attempt -lt 30; $attempt++) {
    $health=Read-LocalJson "$backendUrl/health"
    if ($health -and $health.schema_version -eq '0003_queue_integrity') { break }
    if ($process.HasExited) { throw "Backend stopped. Read $logsDir\backend-error.log." }
    Start-Sleep -Milliseconds 500
  }
  if (!$health -or $health.schema_version -ne '0003_queue_integrity') { throw "Backend did not become ready. Read $logsDir\backend-error.log." }
}
$front = Read-LocalJson "$frontendUrl/api/ready"
if (!$front -or $front.product -ne 'JobPilot AI' -or $front.version -ne '0.3.0' -or $front.demoEnabled -or $front.legacyWorkspaceEnabled) {
  if (Port-InUse $FrontendPort) { throw "Port $FrontendPort is occupied by another or older frontend. Choose another port or stop that instance yourself." }
  $buildId = Join-Path $frontendDir '.next-local\BUILD_ID'
  $buildConfig = Join-Path $frontendDir '.next-local\jobpilot-build.json'
  $needsBuild = !(Test-Path -LiteralPath $buildId)
  if (!$needsBuild) {
    $builtAt = (Get-Item -LiteralPath $buildId).LastWriteTimeUtc
    $sourcePaths = @('app','components','lib','package.json','package-lock.json','next.config.ts') | ForEach-Object { Join-Path $frontendDir $_ } | Where-Object { Test-Path -LiteralPath $_ }
    $changed = Get-ChildItem -LiteralPath $sourcePaths -File -Recurse | Where-Object { $_.LastWriteTimeUtc -gt $builtAt } | Select-Object -First 1
    $needsBuild = [bool]$changed
    try { $config = Get-Content -LiteralPath $buildConfig -Raw | ConvertFrom-Json; if ($config.backend -ne $backendUrl) { $needsBuild=$true } } catch { $needsBuild=$true }
  }
  if ($needsBuild) {
    Push-Location $frontendDir
    try { npm run build; if ($LASTEXITCODE -ne 0) { throw 'Frontend production build failed.' } } finally { Pop-Location }
    @{backend=$backendUrl} | ConvertTo-Json | Set-Content -LiteralPath $buildConfig -Encoding UTF8
  }
  $nextEntry = Join-Path $frontendDir 'node_modules\next\dist\bin\next'
  $nodeExe = (Get-Command node).Source
  $process = Start-Process -FilePath $nodeExe -ArgumentList @(('"'+$nextEntry+'"'),'start','--hostname','127.0.0.1','--port',"$FrontendPort") -WorkingDirectory $frontendDir -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logsDir 'frontend.log') -RedirectStandardError (Join-Path $logsDir 'frontend-error.log')
  $state.frontend = @{pid=$process.Id;started=$process.StartTime.ToUniversalTime().ToString('o')}
  $state | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $statePath -Encoding UTF8
  for ($attempt=0; $attempt -lt 40; $attempt++) {
    $front=Read-LocalJson "$frontendUrl/api/ready"
    if ($front -and $front.version -eq '0.3.0') { break }
    if ($process.HasExited) { throw "Frontend stopped. Read $logsDir\frontend-error.log." }
    Start-Sleep -Milliseconds 500
  }
  if (!$front -or $front.version -ne '0.3.0') { throw "Frontend did not become ready. Read $logsDir\frontend-error.log." }
}
if ($front.demoEnabled -or $front.legacyWorkspaceEnabled) { throw 'The frontend still has a development workspace enabled. Rebuild with the default launcher settings.' }
$proxyHealth = Read-LocalJson "$frontendUrl/api/backend/health"
if (!$proxyHealth -or $proxyHealth.instance_id -ne $expectedInstance) { throw 'The frontend points to another backend instance. Choose a new frontend port or rebuild that frontend with this backend URL.' }
Write-Host "JobPilot AI is ready: $frontendUrl"
Write-Host "Data and logs: $runtimeDir"
Write-Host 'First use: My profile -> verify master CV; Settings -> connect Gmail; Jobs -> find real jobs.'
if ($OpenBrowser) { Start-Process $frontendUrl }
