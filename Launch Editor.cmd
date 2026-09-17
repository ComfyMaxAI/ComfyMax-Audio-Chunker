@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Run setup.ps1 first.
  pause
  exit /b 1
)
start "ComfyMax Audio Chunker" ".venv\Scripts\pythonw.exe" -m comfymax_audio_chunker.editor.marker_app
