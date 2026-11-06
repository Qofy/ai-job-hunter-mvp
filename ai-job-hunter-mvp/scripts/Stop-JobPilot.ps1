param([string]$DataDirectory = '')
$ErrorActionPreference='Stop'
$workspaceDir=[IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
if (!$DataDirectory) { $DataDirectory=if($env:JOBPILOT_DATA_DIR){$env:JOBPILOT_DATA_DIR}else{Join-Path $env:LOCALAPPDATA 'JobPilotAI'} }
$statePath=Join-Path ([IO.Path]::GetFullPath($DataDirectory)) 'launcher.json'
if (!(Test-Path -LiteralPath $statePath)) { Write-Host 'No launcher-owned processes were recorded. Existing servers were left running.';exit }
$state=Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
if ($state.workspace -ne $workspaceDir) { throw 'Launcher state belongs to a different workspace. No process was stopped.' }
foreach($entry in @($state.frontend,$state.backend)) {
  if (!$entry) { continue }
  $process=Get-Process -Id $entry.pid -ErrorAction SilentlyContinue
  if (!$process) { continue }
  $actual=Get-CimInstance Win32_Process -Filter "ProcessId = $($entry.pid)"
  if (!$actual.CommandLine -or $actual.CommandLine.IndexOf($workspaceDir,[StringComparison]::OrdinalIgnoreCase) -lt 0 -or $process.StartTime.ToUniversalTime().Ticks -ne ([datetime]$entry.started).ToUniversalTime().Ticks) {
    Write-Host "Process $($entry.pid) no longer matches the recorded JobPilot process; left running.";continue
  }
  Stop-Process -Id $entry.pid
  Write-Host "Stopped launcher-owned JobPilot process $($entry.pid)."
}
