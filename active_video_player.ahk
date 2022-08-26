#Requires AutoHotkey v2.0-beta

pid := A_Args[1]
if WinWait('ahk_pid ' pid) {
    WinActivate()
    ; WinMinimize()
}