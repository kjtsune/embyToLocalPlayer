@echo OFF
whoami /groups | find "S-1-16-12288" >nul
if ERRORLEVEL 1 (
  echo [ERROR] please run as administrator !!!
  goto END
) else (
  goto BEGIN
)
:BEGIN
if exist "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\embyToLocalPlayer.vbs" (
  del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\embyToLocalPlayer.vbs"
)
cls
echo press a number
echo 1: run in console
echo 2: create and run schtasks
echo 3: stop and delete schtasks
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
echo already copied, paste command is "Ctrl + V"
echo %mainCmd%|clip
GOTO END
:FOUR
echo you have pressed four
python "%~dp0utils/conf_helper.py"
GOTO END
:THREE
echo you have pressed three
schtasks /query /tn embyToLocalPlayer >nul 2>nul
if not ERRORLEVEL 1 (
  schtasks /end /tn embyToLocalPlayer
  schtasks /delete /tn embyToLocalPlayer /f
)
GOTO END
:TWO
echo you have pressed two
set startupVbs="%~dp0embyToLocalPlayer.vbs"
rem echo "%startupVbs%"
echo CreateObject("Wscript.Shell").Run """python"" ""%~dp0embyToLocalPlayer.py""" , 0, True > %startupVbs%
schtasks /create /sc ONLOGON /tn embyToLocalPlayer /tr "wscript.exe \"%~dp0embyToLocalPlayer.vbs"\" /rl HIGHEST /f
schtasks /run /tn embyToLocalPlayer
GOTO END
:ONE
echo you have pressed one
python "%~dp0embyToLocalPlayer.py"
:END

pause
