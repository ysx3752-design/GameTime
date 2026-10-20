#requires -Version 5.1
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$DocxFile = Get-ChildItem (Join-Path $Root "docs") -Filter "*.docx" |
    Where-Object { $_.Name -notlike "~`$*" } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
if (-not $DocxFile) { throw "DOCX not found in docs" }
$Docx = $DocxFile.FullName
$Pdf = [System.IO.Path]::ChangeExtension($Docx, ".pdf")
if (Test-Path $Pdf) { Remove-Item -Force $Pdf }

$Word = New-Object -ComObject Word.Application
$Word.Visible = $false
$Word.DisplayAlerts = 0
try {
    $Document = $Word.Documents.Open($Docx, $false, $true)
    $Document.ExportAsFixedFormat($Pdf, 17)
    $Document.Close(0)
    if (-not (Test-Path $Pdf)) { throw "PDF export failed" }
    $SizeKb = [math]::Round((Get-Item $Pdf).Length / 1KB, 1)
    Write-Host "PDF exported: $Pdf ($($SizeKb) KB)"
} finally {
    $Word.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($Word) | Out-Null
    [GC]::Collect()
}
