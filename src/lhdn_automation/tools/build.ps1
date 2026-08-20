function Assert-Success($message) {
    if ($LASTEXITCODE -ne 0) {
        Write-Error $message
        exit 1
    }
}

# Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser 

$venvDir = ".build-venv"
$venvPython = "$venvDir\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "Creating clean build venv ($venvDir)..." -ForegroundColor Cyan
    python -m venv $venvDir
    Assert-Success "Failed to create the build venv."
}

Write-Host "Installing runtime + build dependencies into $venvDir..." -ForegroundColor Cyan
& $venvPython -m pip install --upgrade pip | Out-Null
& $venvPython -m pip install -r requirements.txt
Assert-Success "pip install -r requirements.txt failed."
& $venvPython -m pip install pyinstaller
Assert-Success "pip install pyinstaller failed."

Write-Host "Syncing version_info.txt with APP_VERSION..." -ForegroundColor Cyan
& $venvPython generate_version_info.py
Assert-Success "Failed to generate version_info.txt - see generate_version_info.py."

Write-Host "Building LHDN-Automation with PyInstaller..." -ForegroundColor Cyan
# --collect-submodules selenium.webdriver.edge is required: selenium's
# webdriver/__init__.py lazily imports browser-specific submodules (e.g.
# selenium.webdriver.edge.options) via __getattr__ at call time, not a
# plain `import` statement PyInstaller's static analysis can see. Without
# this flag, `webdriver.Edge(...)` fails at runtime with
# "ModuleNotFoundError: No module named 'selenium.webdriver.edge.options'".
#
# --noupx and --version-file are both about reducing Windows
# Defender/SmartScreen false positives on an unsigned exe: UPX-compressed
# binaries are a common malware packing signature (explicitly disabled
# here even though nothing currently installs UPX, so it can't silently
# start being used later), and a bare exe with no publisher/product
# metadata at all is one of several things heuristic scanners treat as suspicious.
& $venvPython -m PyInstaller --noconfirm --clean --onedir --windowed --noupx --version-file version_info.txt --name "LHDN_Automation" --collect-submodules selenium.webdriver.edge gui.py
Assert-Success "PyInstaller build failed."

Copy-Item -Path ".envexample" -Destination "dist\LHDN_Automation\.envexample" -Force

$zipPath = "dist\LHDN_Automation.zip"
Remove-Item -Path $zipPath -Force -ErrorAction SilentlyContinue
Compress-Archive -Path "dist\LHDN_Automation\*" -DestinationPath $zipPath
Assert-Success "Failed to zip the build output."

Write-Host ""
Write-Host "Build complete: dist\LHDN_Automation.zip" -ForegroundColor Green
Write-Host "Refer to dist\LHDN_Automation.zip and include the .envexample file."

