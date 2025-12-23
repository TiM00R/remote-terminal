# Build script for remote-terminal-mcp
# Builds distribution package with auto-version detection

# Get script directory (project root)
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "Project Root: $scriptPath" -ForegroundColor White

# Extract version from pyproject.toml
$version = (Get-Content pyproject.toml | Select-String 'version = "(.+)"').Matches.Groups[1].Value

if (-not $version) {
    Write-Host "ERROR: Could not extract version from pyproject.toml" -ForegroundColor Red
    exit 1
}

Write-Host "Auto-detected version: $version" -ForegroundColor Yellow
Write-Host "  Source: pyproject.toml" -ForegroundColor White
Write-Host ""
Write-Host "Building remote-terminal-mcp v$version..." -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

# Clean previous builds
Write-Host "Cleaning previous builds..." -ForegroundColor Yellow
Remove-Item -Recurse -Force dist, build, *.egg-info -ErrorAction SilentlyContinue

# Build package
Write-Host "Building package..." -ForegroundColor Yellow
python -m build

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Green
Write-Host "Build Complete!" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Package Location:" -ForegroundColor Cyan
Write-Host "  dist\remote_terminal_mcp-$version-py3-none-any.whl"
Write-Host "  dist\remote_terminal_mcp-$version.tar.gz"
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. Verify package contents:" -ForegroundColor White
Write-Host "   python -m zipfile -l .\dist\remote_terminal_mcp-$version-py3-none-any.whl | findstr config"
Write-Host ""
Write-Host "2. Create test environment:" -ForegroundColor White
Write-Host "   cd D:\test_pypi_install"
Write-Host "   python -m venv test_env"
Write-Host "   test_env\Scripts\activate"
Write-Host ""
Write-Host "3. Test locally:" -ForegroundColor White
Write-Host "   pip install --force-reinstall $scriptPath\dist\remote_terminal_mcp-$version-py3-none-any.whl"
Write-Host ""
Write-Host "4. Upload to PyPI:" -ForegroundColor White
Write-Host "   twine upload dist/*"
Write-Host ""
Write-Host "5. Update MCP Registry:" -ForegroundColor White
Write-Host "   - Update server.json version to $version"
Write-Host "   - Run: mcp-publisher.exe publish"
Write-Host ""
Write-Host "6. Create GitHub Release:" -ForegroundColor White
Write-Host "   - Tag: v$version"
Write-Host "   - Attach wheel and tar.gz files"
Write-Host ""
Write-Host "======================================================================" -ForegroundColor Green
