# Creates an "HTML Table Generator" desktop shortcut that launches Start Table Generator.bat
# with the Paramount icon. Pin THAT shortcut to your taskbar (right-click > Pin to taskbar)
# for true one-click access.
#
# Run this once: right-click this file > "Run with PowerShell"
# (or in a PowerShell window:  powershell -ExecutionPolicy Bypass -File create-shortcut.ps1)

$ErrorActionPreference = "Stop"

# Folder this script lives in (the table generator folder)
$here    = Split-Path -Parent $MyInvocation.MyCommand.Definition
$bat     = Join-Path $here "Start Table Generator.bat"
$icon    = Join-Path $here "paramount-tablegen.ico"
$desktop = [Environment]::GetFolderPath("Desktop")
$lnkPath = Join-Path $desktop "HTML Table Generator.lnk"

if (-not (Test-Path $bat))  { Write-Error "'Start Table Generator.bat' not found next to this script."; exit 1 }
if (-not (Test-Path $icon)) { Write-Error "paramount-tablegen.ico not found next to this script."; exit 1 }

$shell    = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($lnkPath)
$shortcut.TargetPath       = $bat
$shortcut.WorkingDirectory = $here
$shortcut.IconLocation     = "$icon,0"
$shortcut.WindowStyle      = 7   # start the helper window minimised
$shortcut.Description      = "HTML Table Generator - Paramount Digital"
$shortcut.Save()

Write-Host ""
Write-Host "Created shortcut on your Desktop: 'HTML Table Generator'" -ForegroundColor Green
Write-Host "Right-click it and choose 'Pin to taskbar' to keep the Paramount icon there."
Write-Host ""
