param()

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$OutputRoot = Join-Path $Root "dist-installer"
$Stage = Join-Path $OutputRoot "GT7-Machine-Learning-Tool-Install"
$ZipPath = Join-Path $OutputRoot "GT7-Machine-Learning-Tool-Install.zip"
$AppExe = Join-Path $Root "dist\GT7-Machine-Learning-Tool.exe"

if (-not (Test-Path -LiteralPath $AppExe)) {
    throw "Expected packaged executable was not found: $AppExe"
}

New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null

if (Test-Path -LiteralPath $Stage) {
    $ResolvedStage = (Resolve-Path -LiteralPath $Stage).Path
    $ResolvedOutput = (Resolve-Path -LiteralPath $OutputRoot).Path
    if (-not $ResolvedStage.StartsWith($ResolvedOutput, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove staging path outside output directory: $ResolvedStage"
    }
    Remove-Item -LiteralPath $Stage -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $Stage | Out-Null

Copy-Item -LiteralPath $AppExe -Destination $Stage -Force
Copy-Item -LiteralPath (Join-Path $Root "README.md") -Destination $Stage -Force
Copy-Item -LiteralPath (Join-Path $Root "LICENSE") -Destination $Stage -Force
Copy-Item -LiteralPath (Join-Path $Root "THIRD_PARTY_NOTICES.md") `
    -Destination $Stage `
    -Force
Copy-Item -LiteralPath (Join-Path $Root "docs\Friend_Data_Collection.md") `
    -Destination (Join-Path $Stage "Data Collection Guide.md") `
    -Force
Copy-Item -LiteralPath (Join-Path $Root "installer\manual-install\install.bat") `
    -Destination $Stage `
    -Force
Copy-Item -LiteralPath (Join-Path $Root "installer\manual-install\Install-GT7-Machine-Learning-Tool.ps1") `
    -Destination $Stage `
    -Force

if (Test-Path -LiteralPath $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}

Compress-Archive -Path (Join-Path $Stage "*") -DestinationPath $ZipPath -Force

Write-Host ""
Write-Host "Friend package created:"
Write-Host $ZipPath
