@echo OFF
:BEGIN
cls
echo press a number
echo 1: run in console
echo 2: run in background and add to startup folder
choice /N /C:123 /M "3: open startup folder"%1
IF ERRORLEVEL ==3 GOTO THREE
IF ERRORLEVEL ==2 GOTO TWO
IF ERRORLEVEL ==1 GOTO ONE
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
exit
GOTO END
:ONE
echo you have pressed one
python embyToLocalPlayer.py
:END

pause
