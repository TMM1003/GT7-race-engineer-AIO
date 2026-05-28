param()

$ErrorActionPreference = "Stop"

$SourceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppName = "GT7 Machine Learning Tool"
$AppExe = "GT7-Machine-Learning-Tool.exe"
$BundledAppDirName = "GT7-Machine-Learning-Tool"
$AppDir = Join-Path $env:LOCALAPPDATA "Programs\$AppName"
$DocumentsDir = [Environment]::GetFolderPath("MyDocuments")
$UserAppDir = Join-Path $DocumentsDir $AppName
$RunsDir = Join-Path $UserAppDir "data\runs"
$BundledAppDir = Join-Path $SourceRoot $BundledAppDirName
$BundledAppExe = Join-Path $BundledAppDir $AppExe
$StandaloneAppExe = Join-Path $SourceRoot $AppExe

function Get-DirectorySizeBytes {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return [int64]0
    }

    $measure = Get-ChildItem -LiteralPath $Path -Recurse -File -ErrorAction SilentlyContinue |
        Measure-Object -Property Length -Sum
    return [int64]($measure.Sum ?? 0)
}

function Test-FreeSpaceOrThrow {
    param(
        [string]$InstallPath,
        [int64]$RequiredBytes
    )

    $driveRoot = [System.IO.Path]::GetPathRoot($InstallPath)
    $drive = [System.IO.DriveInfo]::new($driveRoot)
    $freeBytes = [int64]$drive.AvailableFreeSpace
    if ($freeBytes -lt $RequiredBytes) {
        $needGb = [math]::Round($RequiredBytes / 1GB, 2)
        $freeGb = [math]::Round($freeBytes / 1GB, 2)
        throw (
            "Not enough free space on $driveRoot. " +
            "Need about $needGb GB free, but only $freeGb GB is available. " +
            "Free some space on C: and run install again."
        )
    }
}

$payloadBytes =
    if (Test-Path -LiteralPath $BundledAppExe) {
        Get-DirectorySizeBytes -Path $BundledAppDir
    }
    elseif (Test-Path -LiteralPath $StandaloneAppExe) {
        [int64](Get-Item -LiteralPath $StandaloneAppExe).Length
    }
    else {
        0
    }

if ($payloadBytes -le 0) {
    throw "Packaged app was not found. Expected either '$BundledAppExe' or '$StandaloneAppExe'."
}

# Reserve extra headroom so the install does not fail midway on a nearly full
# system drive.
$requiredBytes = $payloadBytes + 1GB
Test-FreeSpaceOrThrow -InstallPath $AppDir -RequiredBytes $requiredBytes

if (Test-Path -LiteralPath $AppDir) {
    $ResolvedAppDir = (Resolve-Path -LiteralPath $AppDir).Path
    $ResolvedProgramsDir = (Resolve-Path -LiteralPath (Join-Path $env:LOCALAPPDATA "Programs")).Path
    if (-not $ResolvedAppDir.StartsWith($ResolvedProgramsDir, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove install path outside LocalAppData Programs: $ResolvedAppDir"
    }
    Remove-Item -LiteralPath $AppDir -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $AppDir | Out-Null
New-Item -ItemType Directory -Force -Path $RunsDir | Out-Null

if (Test-Path -LiteralPath $BundledAppExe) {
    Copy-Item -Path (Join-Path $BundledAppDir "*") -Destination $AppDir -Recurse -Force
}
elseif (Test-Path -LiteralPath $StandaloneAppExe) {
    Copy-Item -LiteralPath $StandaloneAppExe -Destination $AppDir -Force
}
else {
    throw "Packaged app was not found. Expected either '$BundledAppExe' or '$StandaloneAppExe'."
}

Copy-Item -LiteralPath (Join-Path $SourceRoot "README.md") -Destination $AppDir -Force
Copy-Item -LiteralPath (Join-Path $SourceRoot "Participant_Guide.md") -Destination $AppDir -Force

function New-AppShortcut {
    param(
        [string]$ShortcutPath,
        [string]$TargetPath,
        [string]$WorkingDirectory
    )

    $Shell = New-Object -ComObject WScript.Shell
    $Shortcut = $Shell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = $TargetPath
    $Shortcut.WorkingDirectory = $WorkingDirectory
    $Shortcut.Save()
}

$TargetExe = Join-Path $AppDir $AppExe
$StartMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\$AppName"
$DesktopDir = [Environment]::GetFolderPath("DesktopDirectory")
New-Item -ItemType Directory -Force -Path $StartMenuDir | Out-Null

New-AppShortcut `
    -ShortcutPath (Join-Path $StartMenuDir "$AppName.lnk") `
    -TargetPath $TargetExe `
    -WorkingDirectory $UserAppDir

New-AppShortcut `
    -ShortcutPath (Join-Path $DesktopDir "$AppName.lnk") `
    -TargetPath $TargetExe `
    -WorkingDirectory $UserAppDir

New-AppShortcut `
    -ShortcutPath (Join-Path $StartMenuDir "Open Collected Runs Folder.lnk") `
    -TargetPath $RunsDir `
    -WorkingDirectory $UserAppDir

Write-Host ""
Write-Host "$AppName installed."
Write-Host "App:  $TargetExe"
Write-Host "Runs: $RunsDir"
