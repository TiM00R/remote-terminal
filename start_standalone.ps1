# Remote Terminal - Standalone Mode Startup Script
# This script will be in standalone/ folder after reorganization
# Run from project root: .\standalone\start_standalone.ps1

# $projectRoot = Split-Path -Parent $PSScriptRoot
$projectRoot = $PSScriptRoot

$venvPath = Join-Path $projectRoot ".venv"
$requirementsPath = Join-Path $projectRoot "requirements.txt"
$scriptPath = Join-Path $PSScriptRoot "standalone\standalone_mcp.py"

Write-Host ""
Write-Host "PSScriptRoot: $PSScriptRoot"
Write-Host "projectRoot: $projectRoot"
Write-Host "venvPath: $venvPath"
Write-Host "requirementsPath: $requirementsPath"
Write-Host "scriptPath: $scriptPath"
Write-Host ""
# exit

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Remote Terminal - Standalone Mode" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Check if virtual environment exists
if (-not (Test-Path -LiteralPath $venvPath)){

    Write-Host "Virtual environment not found. Setting up for first time..." -ForegroundColor Yellow
    Write-Host ""
     
    # Create virtual environment
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv $venvPath
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to create virtual environment" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "Virtual environment created!" -ForegroundColor Green
    Write-Host ""
    
    # Activate virtual environment
    Write-Host "Activating virtual environment..." -ForegroundColor Yellow
    & "$venvPath\Scripts\Activate.ps1"
    
    # Install dependencies
    Write-Host "Installing dependencies (this may take a minute)..." -ForegroundColor Yellow
    pip install --upgrade pip
    pip install -r $requirementsPath
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to install dependencies" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "Dependencies installed!" -ForegroundColor Green
    Write-Host ""
    
} else {
    # Virtual environment exists - just activate it
    Write-Host "Virtual environment found. Activating..." -ForegroundColor Green
    & "$venvPath\Scripts\Activate.ps1"
    Write-Host ""
}

# Verify standalone script exists
if (-not (Test-Path $scriptPath)) {
    Write-Host "ERROR: Cannot find standalone_mcp.py" -ForegroundColor Red
    Write-Host "Expected at: $scriptPath" -ForegroundColor Red
    exit 1
}

Write-Host "============================================================" -ForegroundColor Green
Write-Host " Starting Standalone Mode..." -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Mode: Standalone (Manual MCP Tool Execution)" -ForegroundColor Cyan
Write-Host ""
Write-Host "Expected URLs:" -ForegroundColor Cyan
Write-Host "  Control Panel: http://localhost:8081 (All 35 Tools)" -ForegroundColor Yellow
Write-Host "  Web Terminal:  http://localhost:8082" -ForegroundColor Yellow
Write-Host ""
Write-Host "Both will open automatically in your browser" -ForegroundColor Gray
Write-Host ""
Write-Host "Press Ctrl+C to stop..." -ForegroundColor Gray
Write-Host ""

# Run the standalone script
python $scriptPath
