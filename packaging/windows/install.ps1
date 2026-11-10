# Install predimrc_wrapper for the current user, without administrator rights.
# Keep this file ASCII: Windows PowerShell 5.1 reads a script without BOM as ANSI.
param(
    [string]$AppDir = (Join-Path $env:LOCALAPPDATA "Programs\predimrc_wrapper"),
    [string]$WorkDir = (Join-Path ([Environment]::GetFolderPath("MyDocuments")) "predimrc_wrapper"),
    [switch]$NoShortcut,
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"
$ShortcutName = "PredimRC wrapper.lnk"
$PythonVersion = "3.12"

function Invoke-Uv {
    & $script:Uv @args
    if ($LASTEXITCODE -ne 0) {
        throw "uv $($args -join ' ') failed with exit code $LASTEXITCODE."
    }
}

try {
    # A downloaded zip marks its files as coming from the Internet.
    Get-ChildItem -Path $PSScriptRoot -Recurse -File | Unblock-File

    $script:Uv = Join-Path $PSScriptRoot "uv.exe"
    $wheel = Get-ChildItem -Path $PSScriptRoot -Filter "*.whl" | Select-Object -First 1
    if ($null -eq $wheel) { throw "No wheel next to install.ps1: extract the whole zip." }

    New-Item -ItemType Directory -Force -Path $AppDir | Out-Null
    $profiles = Join-Path $WorkDir "profiles"
    New-Item -ItemType Directory -Force -Path $profiles | Out-Null

    $env:UV_PYTHON_INSTALL_DIR = Join-Path $AppDir "python"
    $env:UV_CACHE_DIR = Join-Path $AppDir "cache"
    $env:UV_PYTHON_PREFERENCE = "only-managed"
    $venv = Join-Path $AppDir "venv"
    $python = Join-Path $venv "Scripts\python.exe"

    Write-Host "[1/4] Installing Python $PythonVersion in $AppDir"
    Invoke-Uv python install $PythonVersion --no-bin --no-registry
    Invoke-Uv venv $venv --python $PythonVersion --clear

    Write-Host "[2/4] Installing the dependencies (internet access needed, several minutes)"
    Invoke-Uv pip install --python $python --require-hashes -r (Join-Path $PSScriptRoot "requirements.txt")
    Invoke-Uv pip install --python $python --no-deps $wheel.FullName

    Write-Host "[3/4] Finishing the installation"
    # The packages are hard links or copies: the cache is not needed any more.
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $env:UV_CACHE_DIR
    Copy-Item -Force (Join-Path $PSScriptRoot "uninstall.bat") $AppDir
    Copy-Item -Force (Join-Path $PSScriptRoot "THIRD_PARTY_NOTICES.md") $AppDir
    Copy-Item -Force (Join-Path $PSScriptRoot "LICENSE.txt") $AppDir
    Copy-Item -Force -Recurse (Join-Path $PSScriptRoot "LICENSES") $AppDir

    # Without this file, Streamlit waits on the console for an e-mail address at first launch.
    $streamlitHome = Join-Path $env:USERPROFILE ".streamlit"
    $credentials = Join-Path $streamlitHome "credentials.toml"
    if (-not (Test-Path $credentials)) {
        New-Item -ItemType Directory -Force -Path $streamlitHome | Out-Null
        Set-Content -Path $credentials -Encoding Ascii -Value "[general]`r`nemail = `"`""
    }

    $ui = Join-Path $venv "Scripts\predimrc-ui.exe"
    $uiArgs = "--browser.gatherUsageStats=false"
    if (-not $NoShortcut) {
        $desktop = [Environment]::GetFolderPath("Desktop")
        $shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $desktop $ShortcutName))
        $shortcut.TargetPath = $ui
        $shortcut.Arguments = $uiArgs
        $shortcut.WorkingDirectory = $WorkDir
        $shortcut.Description = "Pre-sizing of RC VTOL aircraft (close the console window to stop)"
        $shortcut.Save()
    }

    Write-Host "[4/4] Checking the PredimRC prerequisites"
    # Workbooks shipped with their notice (build_zip.py --predimrc-notice); never replaced.
    $bundled = Join-Path $PSScriptRoot "predimrc"
    if (Test-Path $bundled) {
        Get-ChildItem -Path $bundled -File -Filter "PredimRC_*" |
            Where-Object { -not (Test-Path (Join-Path $profiles $_.Name)) } |
            Copy-Item -Destination $profiles
    }
    if (-not (Test-Path "Registry::HKEY_CLASSES_ROOT\Excel.Application")) {
        Write-Warning "Microsoft Excel was not found: the quadplane aerodynamics (PredimRC) will not run."
    }
    if (-not (Get-ChildItem -Path $profiles -File -Filter "PredimRC_*")) {
        Write-Host ""
        Write-Host "PredimRC is not included. The quadplane architecture needs it (multicopters do not):"
        Write-Host "get PredimRC from its author, then copy it into this folder as PredimRC_<profile>.xls:"
        Write-Host "  $profiles"
    }

    Write-Host ""
    Write-Host "Installation complete. Your studies are stored in $WorkDir"
    if (-not $NoLaunch) {
        Start-Process -FilePath $ui -ArgumentList $uiArgs -WorkingDirectory $WorkDir
    }
    exit 0
}
catch {
    Write-Host ""
    Write-Host "Installation failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "If the application is running, close it and run install.bat again."
    exit 1
}
