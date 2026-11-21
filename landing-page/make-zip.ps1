$ProgressPreference = 'SilentlyContinue'
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$sourceDir = "c:\Users\USER\abdallh\dist"
$zipPath1 = "c:\Users\USER\abdallh\dist.zip"
$zipPath2 = "c:\Users\USER\abdallh\landing-page-netlify.zip"
$zipPath3 = "c:\Users\USER\abdallh\landing-page\dist.zip"

if (Test-Path $zipPath1) { Remove-Item $zipPath1 -Force }
if (Test-Path $zipPath2) { Remove-Item $zipPath2 -Force }
if (Test-Path $zipPath3) { Remove-Item $zipPath3 -Force }

$zipFile = [System.IO.Compression.ZipFile]::Open($zipPath1, [System.IO.Compression.ZipArchiveMode]::Create)
$files = Get-ChildItem -Path $sourceDir -Recurse -File

foreach ($file in $files) {
    $relPath = $file.FullName.Substring($sourceDir.Length + 1).Replace('\', '/')
    [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zipFile, $file.FullName, $relPath, [System.IO.Compression.CompressionLevel]::Optimal) | Out-Null
}

$zipFile.Dispose()

Copy-Item $zipPath1 $zipPath2 -Force
Copy-Item $zipPath1 $zipPath3 -Force

Write-Output "ZIP_CREATED_SUCCESSFULLY"
