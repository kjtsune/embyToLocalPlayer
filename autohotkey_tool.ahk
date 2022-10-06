#Requires AutoHotkey v2.0-beta
#SingleInstance force

opetation :=  A_Args[1]

activateWindowsByPid(pid) {
    win_title := 'ahk_pid ' pid
    try {
        if WinWait(win_title, , 30) {
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
    } catch TargetError {
        Exit(0)
    }
}

if (opetation == 'activate') {
    ; MsgBox(A_Args[2])
    activateWindowsByPid(A_Args[2])
}
