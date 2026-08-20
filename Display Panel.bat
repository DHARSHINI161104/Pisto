@echo off
rem Display Panel - double-click to open the standalone desktop GUI.
rem This launches the native PySide6 application (no browser, no web server,
rem no URL). It works in demo mode without a camera and shows the live OpenCV
rem preview automatically when a camera is connected.
rem RIFLE_DEMO_CAMERA=1 shows the live OpenCV target view even when no real
rem camera is connected (auto-disabled when a real webcam is detected).
cd /d "%~dp0"
set RIFLE_DEMO_CAMERA=1
start "" ".\.venv\Scripts\pythonw.exe" "main.py"