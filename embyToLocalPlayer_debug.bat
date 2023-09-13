@echo OFF

:BEGIN
cls

for /F "usebackq tokens=*" %%A in (`python --version 2^>^&1`) do set PYTHON_VERSION=%%A

if "%PYTHON_VERSION:~0,6%" == "Python" (
    echo %PYTHON_VERSION%
    python -c "import sys; print(sys.executable)"
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
python utils/update.py
GOTO END


:FIVE
echo you have pressed five
set mainCmd=python "%cd%\embyToLocalPlayer.py"
echo %mainCmd%
echo already copied, paste command is "Ctrl + V"
echo %mainCmd%|clip
GOTO END


:FOUR
echo you have pressed four
python utils/conf_helper.py
GOTO END


:THREE
echo you have pressed three
explorer shell:startup
GOTO END


:TWO
echo you have pressed two
set startupVbs="%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\embyToLocalPlayer.vbs"
rem echo "%startupVbs%"
echo CreateObject("Wscript.Shell").Run """python"" ""%cd%\embyToLocalPlayer.py""" , 0, True > %startupVbs%
echo close this window manually
wscript.exe ""%startupVbs%""
GOTO END


:ONE
echo you have pressed one
python embyToLocalPlayer.py
GOTO END


:END
echo all tasks are finished.
pause
