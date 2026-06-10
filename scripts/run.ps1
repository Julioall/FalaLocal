$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

$PythonBin = Join-Path $RootDir ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonBin)) {
    throw "Ambiente nao encontrado. Execute .\scripts\bootstrap.ps1 primeiro."
}

if (-not $env:PIPER_ESPEAK) {
    $Candidates = @()
    if ($env:ProgramFiles) {
        $Candidates += Join-Path $env:ProgramFiles "eSpeak NG\espeak-ng.exe"
    }
    if (${env:ProgramFiles(x86)}) {
        $Candidates += Join-Path ${env:ProgramFiles(x86)} "eSpeak NG\espeak-ng.exe"
    }
    if ($env:LOCALAPPDATA) {
        $Candidates += Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages\eSpeak-NG.eSpeak-NG_*\*\espeak-ng.exe"
        $Candidates += Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages\eSpeak-NG.eSpeak-NG_*\espeak-ng.exe"
    }
    foreach ($Candidate in $Candidates) {
        $Match = Get-Item $Candidate -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($Match) {
            $env:PIPER_ESPEAK = $Match.FullName
            break
        }
    }
}

& $PythonBin -m piper_ptbr_desktop
