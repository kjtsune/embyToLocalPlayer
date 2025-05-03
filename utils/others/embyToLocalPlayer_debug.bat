@echo OFF
chcp 65001
:BEGIN
cls

set pythonPath="python"
set pythonEmbed="%~dp0python_embed\python.exe"
if exist %pythonEmbed% (
    echo use python embed. %pythonEmbed%
    set pythonPath=%pythonEmbed%
)

for /F "usebackq tokens=*" %%A in (`%pythonPath% --version 2^>^&1`) do set PYTHON_VERSION=%%A

if "%PYTHON_VERSION:~0,6%" == "Python" (
    echo %PYTHON_VERSION%
    %pythonPath% -c "import sys; print(sys.executable)"
    echo press a number
    echo 1: run in console
    echo 2: run in background and add to startup folder
    echo 3: open startup folder
    echo 4: path translate helper
    echo 5: copy script path to clipboard
    echo 6: update to latest version
    choice /N /C:123456 /M "press a number"%1
    IF ERRORLEVEL ==6 GOTO SIX
    IF ERRORLEVEL ==5 GOTO FIVE
    IF ERRORLEVEL ==4 GOTO FOUR
    IF ERRORLEVEL ==3 GOTO THREE
    IF ERRORLEVEL ==2 GOTO TWO
    IF ERRORLEVEL ==1 GOTO ONE
    GOTO END
) else (
    echo ERROR: python not found, reinstall it and add to path!
    GOTO END
)


:SIX
echo you have pressed six
%pythonPath% "%~dp0utils/update.py"
GOTO END


:FIVE
echo you have pressed five
set mainCmd=%pythonPath% "%~dp0embyToLocalPlayer.py"
echo %mainCmd%
echo already copied, run in cmd, not powershell. paste command is "Ctrl + V"
echo %mainCmd%|clip
GOTO END


:FOUR
echo you have pressed four
%pythonPath% "%~dp0utils/conf_helper.py"
GOTO END


:THREE
echo you have pressed three
explorer shell:startup
GOTO END


:TWO
echo you have pressed two
set startupVbs="%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\embyToLocalPlayer.vbs"
set startupCmd=CreateObject("Wscript.Shell").Run ""%pythonPath%" ""%~dp0embyToLocalPlayer.py""" , 0, True
echo startupCmd=%startupCmd%
echo startupVbs=%startupVbs%
echo %startupCmd% > %startupVbs%
echo writing startupCmd to startupVbs, save in startup folder.
timeout /nobreak /t 1 >nul
echo close this window manually
cscript.exe //nologo ""%startupVbs%""
GOTO END


:ONE
echo you have pressed one
%pythonPath% "%~dp0embyToLocalPlayer.py"
GOTO END


:END
echo all tasks are finished.
pause
