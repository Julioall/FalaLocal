$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Instalando uv..."
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $env:Path = "$env:USERPROFILE\.local\bin;$env:USERPROFILE\.cargo\bin;$env:Path"
}

uv venv .venv --python 3.10
$PythonBin = Join-Path $RootDir ".venv\Scripts\python.exe"

& $PythonBin -m pip install --upgrade pip
uv pip install --python $PythonBin -e .

$EspeakCommand = Get-Command espeak-ng -ErrorAction SilentlyContinue
$EspeakCandidates = @()
if ($env:ProgramFiles) {
    $EspeakCandidates += Join-Path $env:ProgramFiles "eSpeak NG\espeak-ng.exe"
}
if (${env:ProgramFiles(x86)}) {
    $EspeakCandidates += Join-Path ${env:ProgramFiles(x86)} "eSpeak NG\espeak-ng.exe"
}
if ($env:LOCALAPPDATA) {
    $EspeakCandidates += Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages\eSpeak-NG.eSpeak-NG_*\*\espeak-ng.exe"
    $EspeakCandidates += Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages\eSpeak-NG.eSpeak-NG_*\espeak-ng.exe"
}
$EspeakPath = $null
foreach ($Candidate in $EspeakCandidates) {
    $Match = Get-Item $Candidate -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($Match) {
        $EspeakPath = $Match.FullName
        break
    }
}

if (-not $EspeakCommand -and -not $EspeakPath) {
    Write-Host ""
    Write-Host "Aviso: espeak-ng nao foi encontrado no PATH."
    Write-Host "Opcao rapida: winget install -e --id eSpeak-NG.eSpeak-NG"
    Write-Host "Alternativa: baixe o MSI em https://github.com/espeak-ng/espeak-ng/releases"
} elseif ($EspeakPath) {
    Write-Host ""
    Write-Host "eSpeak NG encontrado fora do PATH: $EspeakPath"
    Write-Host "O run.ps1 vai usar esse caminho automaticamente."
}

Write-Host ""
Write-Host "Ambiente pronto. Execute: powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1"
