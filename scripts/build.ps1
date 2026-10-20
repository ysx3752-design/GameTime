#requires -Version 5.1
<#
    Build the portable Windows x64 package for GameTime.
    Usage: powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1
#>
param(
    [switch]$SkipSmoke
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

Write-Host "==> Cleaning previous build" -ForegroundColor Cyan
if (Test-Path "dist\GameTime") { Remove-Item -Recurse -Force "dist\GameTime" }
if (Test-Path "build\pyinstaller") { Remove-Item -Recurse -Force "build\pyinstaller" }

Write-Host "==> Running PyInstaller" -ForegroundColor Cyan
python -m PyInstaller --noconfirm --clean --distpath "dist" --workpath "build\pyinstaller" "GameTime.spec"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed ($LASTEXITCODE)" }

$Exe = Join-Path $Root "dist\GameTime\GameTime.exe"
if (-not (Test-Path $Exe)) { throw "Build output missing: $Exe" }

if (-not $SkipSmoke) {
    Write-Host "==> Running packaged smoke test" -ForegroundColor Cyan
    $SmokeDir = Join-Path $Root "build\packaged-smoke-data"
    if (Test-Path $SmokeDir) { Remove-Item -Recurse -Force $SmokeDir }
    $SmokeOutput = Join-Path $Root "build\packaged-smoke.json"
    if (Test-Path $SmokeOutput) { Remove-Item -Force $SmokeOutput }
    $Process = Start-Process -FilePath $Exe -ArgumentList @(
        "--smoke-test",
        "--data-dir", $SmokeDir,
        "--smoke-output", $SmokeOutput
    ) -PassThru -Wait
    if ($Process.ExitCode -ne 0) { throw "Packaged smoke test failed, exit code $($Process.ExitCode)" }
    if (-not (Test-Path $SmokeOutput)) { throw "Packaged smoke test produced no result file" }
    $Result = Get-Content $SmokeOutput -Raw | ConvertFrom-Json
    if (-not $Result.ok) { throw "Packaged smoke test did not pass: $SmokeOutput" }
    Write-Host "    OK: v$($Result.version), data dir $($Result.data_dir)" -ForegroundColor Green
}

Write-Host "==> Copying documentation and notices" -ForegroundColor Cyan
$Dist = Join-Path $Root "dist\GameTime"
Copy-Item (Join-Path $Root "docs") (Join-Path $Dist "docs") -Recurse -Force
Copy-Item (Join-Path $Root "LICENSES") (Join-Path $Dist "LICENSES") -Recurse -Force
Copy-Item (Join-Path $Root "README.md") (Join-Path $Dist "README.md") -Force
Copy-Item (Join-Path $Root "THIRD_PARTY_NOTICES.md") (Join-Path $Dist "THIRD_PARTY_NOTICES.md") -Force

Write-Host "==> Creating portable ZIP" -ForegroundColor Cyan
$Zip = Join-Path $Root "dist\GameTime-1.1.2-win64-portable.zip"
if (Test-Path $Zip) { Remove-Item -Force $Zip }
Compress-Archive -Path (Join-Path $Root "dist\GameTime") -DestinationPath $Zip -CompressionLevel Optimal

$TotalMb = [math]::Round((Get-ChildItem "dist\GameTime" -Recurse -File | Measure-Object Length -Sum).Sum / 1MB, 1)
$ZipMb = [math]::Round((Get-Item $Zip).Length / 1MB, 1)
$ExeHash = (Get-FileHash $Exe -Algorithm SHA256).Hash
$ZipHash = (Get-FileHash $Zip -Algorithm SHA256).Hash
$ChecksumPath = Join-Path $Root "dist\SHA256SUMS.txt"
@(
    "SHA256  GameTime.exe  $ExeHash",
    "SHA256  GameTime-1.1.2-win64-portable.zip  $ZipHash"
) | Set-Content -Path $ChecksumPath -Encoding ASCII

Write-Host ""
Write-Host "Build complete" -ForegroundColor Green
Write-Host "  EXE: dist\GameTime\GameTime.exe"
Write-Host "  ZIP: dist\GameTime-1.1.2-win64-portable.zip ($($ZipMb) MB)"
Write-Host "  Folder size: $($TotalMb) MB"
Write-Host "  SHA256: $ChecksumPath"
