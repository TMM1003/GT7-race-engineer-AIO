param(
    [switch]$SkipPyInstaller
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

if (-not $SkipPyInstaller) {
    & "$Root\package.bat"
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller packaging failed with exit code $LASTEXITCODE."
    }
}

$AppExe = Join-Path $Root "dist\GT7-Machine-Learning-Tool\GT7-Machine-Learning-Tool.exe"
if (-not (Test-Path -LiteralPath $AppExe)) {
    throw "Expected packaged application executable was not found: $AppExe"
}

$IsccCandidates = @()
$Command = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
if ($Command) {
    $IsccCandidates += $Command.Source
}
$IsccCandidates += @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
)

$Iscc = $IsccCandidates |
    Where-Object { $_ -and (Test-Path -LiteralPath $_) } |
    Select-Object -First 1

if (-not $Iscc) {
    throw "Inno Setup 6 compiler was not found. Install Inno Setup, then run this script again, or run build_friend_package.bat for the zip-based installer package."
}

$InstallerScript = Join-Path $Root "installer\gt7-machine-learning-tool.iss"
& $Iscc $InstallerScript
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup failed with exit code $LASTEXITCODE."
}

Write-Host ""
Write-Host "Installer created in: $Root\dist-installer"
