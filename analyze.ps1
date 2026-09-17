param(
    [Parameter(Mandatory=$true)][string]$Song,
    [string]$Output,
    [ValidateSet('auto','cpu','cuda')][string]$Device = 'auto',
    [string]$Model = 'small',
    [string]$Language,
    [switch]$Offline
)
$ErrorActionPreference = 'Stop'
$PythonExe = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $PythonExe)) { throw 'Run setup.ps1 first.' }
$CliArgs = @('-m','comfymax_audio_chunker',$Song,'--device',$Device,'--model',$Model)
if ($Output) { $CliArgs += @('--output',$Output) }
if ($Language) { $CliArgs += @('--language',$Language) }
if ($Offline) { $CliArgs += '--offline' }
& $PythonExe @CliArgs
if ($LASTEXITCODE -ne 0) { throw "Analysis failed ($LASTEXITCODE). See the run's analysis.log." }
