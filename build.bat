@echo off
setlocal
cd /d "%~dp0"
echo Instalando dependencias...
python -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo Gerando .exe...
python -m PyInstaller --noconsole --onefile --name UIsername --icon "ui\app.ico" --add-data "ui;ui" --collect-all webview app.py
if errorlevel 1 goto failed
echo.
echo Pronto! O executavel esta em: dist\UIsername.exe
echo Os dados ficam em %%LOCALAPPDATA%%\UIsername, na conta de cada usuario.
pause
exit /b 0
:failed
echo.
echo Falha na instalacao ou compilacao. Confira a mensagem acima.
pause
exit /b 1
