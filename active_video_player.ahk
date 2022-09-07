#Requires AutoHotkey v2.0-beta

pid := A_Args[1]
win_title := 'ahk_pid ' pid
if WinWait(win_title, , 3000) {
    WinActivate()
    WinMoveTop()
    processName := WinGetProcessName()
    if (processName = 'mpv.exe') {
        ; if (processName = 'mpv.exe' or InStr(processName, 'mpc-hc')){
        WinSetAlwaysOnTop(1, win_title)
        ; WinSetAlwaysOnTop(0, win_title)
        ; MsgBox('found')
    }
}