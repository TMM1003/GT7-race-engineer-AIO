param()

$ErrorActionPreference = "Stop"

$SourceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppName = "GT7 Machine Learning Tool"
$AppExe = "GT7-Machine-Learning-Tool.exe"
$AppDir = Join-Path $env:LOCALAPPDATA "Programs\$AppName"
$DocumentsDir = [Environment]::GetFolderPath("MyDocuments")
$UserAppDir = Join-Path $DocumentsDir $AppName
$RunsDir = Join-Path $UserAppDir "data\runs"

New-Item -ItemType Directory -Force -Path $AppDir | Out-Null
New-Item -ItemType Directory -Force -Path $RunsDir | Out-Null

Copy-Item -LiteralPath (Join-Path $SourceRoot $AppExe) -Destination $AppDir -Force
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
