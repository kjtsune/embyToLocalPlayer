@echo OFF
:BEGIN
cls
echo press a number
echo 1: run in console
echo 2: run in background and add to startup folder
echo 3: open startup folder
echo 4: path translate helper
echo 5: copy script path to clipboard
choice /N /C:12345 /M "press a number"%1
IF ERRORLEVEL ==5 GOTO FIVE
IF ERRORLEVEL ==4 GOTO FOUR
IF ERRORLEVEL ==3 GOTO THREE
IF ERRORLEVEL ==2 GOTO TWO
IF ERRORLEVEL ==1 GOTO ONE
GOTO END
:FIVE
echo you have pressed five
set mainCmd=python "%~dp0embyToLocalPlayer.py"
echo %mainCmd%
echo already copied, pause command is "Ctrl + V"
echo %mainCmd%|clip
GOTO END
:FOUR
echo you have pressed four
python "%~dp0utils/conf_helper.py"
GOTO END
:THREE
echo you have pressed three
explorer shell:startup
GOTO END
:TWO
echo you have pressed two
set startupVbs="%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\embyToLocalPlayer.vbs"
rem echo "%startupVbs%"
echo CreateObject("Wscript.Shell").Run """python"" ""%~dp0embyToLocalPlayer.py""" , 0, True > %startupVbs%
echo close this window manually
wscript.exe ""%startupVbs%""
exit
GOTO END
:ONE
echo you have pressed one
python "%~dp0embyToLocalPlayer.py"
:END

pause
