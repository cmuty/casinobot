# PowerShell script to start Casino Bot
Write-Host "Starting Casino Bot..." -ForegroundColor Green
Write-Host ""

# Check if virtual environment exists
if (Test-Path "venv\Scripts\Activate.ps1") {
    Write-Host "Activating virtual environment..." -ForegroundColor Yellow
    & .\venv\Scripts\Activate.ps1
} else {
    Write-Host "Virtual environment not found! Creating..." -ForegroundColor Red
    python -m venv venv
    & .\venv\Scripts\Activate.ps1
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    pip install -r requirements.txt
}

# Run the bot
Write-Host ""
Write-Host "Running bot..." -ForegroundColor Green
python main.py

# Keep window open if there's an error
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Bot stopped with an error!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
}

