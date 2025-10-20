@echo off
echo Starting Casino Bot...
echo.

REM Activate virtual environment
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo Virtual environment not found! Creating...
    python -m venv venv
    call venv\Scripts\activate.bat
    echo Installing dependencies...
    pip install -r requirements.txt
)

REM Run the bot
echo.
echo Running bot...
python main.py

REM Keep window open if there's an error
if errorlevel 1 (
    echo.
    echo Bot stopped with an error!
    pause
)

