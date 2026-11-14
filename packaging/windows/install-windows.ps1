# One-line installer of predim-vtol for Windows, published with each release:
#   powershell -ExecutionPolicy ByPass -c "irm https://github.com/SebastienBocquet/predim-vtol/releases/latest/download/install-windows.ps1 | iex"
# Downloads the Windows zip of the release and runs its install.ps1 (no administrator rights).
# Keep this file ASCII: Windows PowerShell 5.1 reads a script without BOM as ANSI.
# The release workflow replaces @VERSION@ by the released version.

$ErrorActionPreference = "Stop"
$Version = if ($env:PREDIM_VTOL_VERSION) { $env:PREDIM_VTOL_VERSION } else { "@VERSION@" }
$Name = "predim-vtol-$Version-windows"
$Url = "https://github.com/SebastienBocquet/predim-vtol/releases/download/v$Version/$Name.zip"
$Temp = Join-Path $env:TEMP $Name

# GitHub needs TLS 1.2, not always enabled in Windows PowerShell 5.1.
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor 3072
# The progress bar makes Invoke-WebRequest many times slower.
$ProgressPreference = "SilentlyContinue"

Write-Host "Downloading predim-vtol $Version"
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $Temp
New-Item -ItemType Directory -Force -Path $Temp | Out-Null
$Zip = Join-Path $Temp "$Name.zip"
Invoke-WebRequest -Uri $Url -OutFile $Zip -UseBasicParsing
Expand-Archive -Path $Zip -DestinationPath $Temp -Force

& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Temp "$Name\install.ps1")
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installation failed. The downloaded files are in $Temp" -ForegroundColor Red
}
