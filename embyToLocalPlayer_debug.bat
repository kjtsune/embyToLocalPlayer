@echo OFF
:BEGIN
cls
echo press a number
echo 1: run in debug mode
choice /N /C:123 /M "2: add to startup folder and run in background"%1
IF ERRORLEVEL ==3 GOTO THREE
IF ERRORLEVEL ==2 GOTO TWO
IF ERRORLEVEL ==1 GOTO ONE
GOTO END
:THREE
echo you have preesed three
GOTO END
:TWO
echo you have preesed two
set startupVbs="%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\embyToLocalPlayer.vbs"
rem echo "%startupVbs%"
echo CreateObject("Wscript.Shell").Run """python"" ""%cd%\embyToLocalPlayer.py""" , 0, True > %startupVbs%
explorer shell:startup
echo close this window manually
wscript.exe ""%startupVbs%""
exit
GOTO END
:ONE
echo you have preesed one
python embyToLocalPlayer.py
:END

