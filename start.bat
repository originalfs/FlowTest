@echo off
REM Double-click this file (or run it) to start LocalFlow.
REM Works from anywhere: %~dp0 always resolves to this script's own folder.

cd /d "%~dp0"

if not exist venv\Scripts\activate.bat (
    echo Virtual environment not found in %~dp0venv
    echo Run this first: py -3 -m venv venv ^&^& venv\Scripts\activate ^&^& pip install -e .
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

REM Makes the CUDA DLLs installed by "pip install nvidia-cublas-cu12 nvidia-cudnn-cu12"
REM discoverable. Harmless if you're running on CPU or haven't installed them.
set "PATH=%PATH%;%~dp0venv\Lib\site-packages\nvidia\cublas\bin;%~dp0venv\Lib\site-packages\nvidia\cudnn\bin"

localflow

echo.
echo LocalFlow has stopped.
pause
