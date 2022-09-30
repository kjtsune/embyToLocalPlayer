#Requires AutoHotkey v2.0-beta

ArgsArrayToString(Args) {
    Result := ''
    For value in Args {
        if (InStr(value, ' ')) {
            value := '"' value '"'
        }
        if (A_Index != Args.Length)
            value .= ' '
        Result .= value
    }

    return Result
}
CopySelfToDebugOrNot() {
    if (InStr(A_ScriptName, 'python_runner')) {
        name := InputBox('1: 输入需要运行的python文件名 `n'
            '2: 与同名python脚本放一起`n'
            '3: 默认隐藏窗口，需要窗口则运行debug'
        ).value
        if (name == '') {
            MsgBox('输入为空')
            Exit()
        }
        if (RegExMatch(name, '.py$')) {
            name := StrReplace(name, '.py', '')
        }
        fileType := StrSplit(A_ScriptName, '.')[-1]
        FileCopy(A_ScriptFullPath, name '_hide.' fileType, true)
        FileCopy(A_ScriptFullPath, name '_debug.' fileType, true)
        Exit()
    }

}
CopySelfToDebugOrNot()
hideOrNot := InStr(A_ScriptFullPath, '_debug') ? '' : 'hide'
argument := ArgsArrayToString(A_Args)
pythonScriptPath := RegExReplace(A_ScriptFullPath, '(_hide|_debug)', '')
pythonScriptPath := RegExReplace(pythonScriptPath, '(exe|ahk)$', 'py')
cmd := 'python ' '"' pythonScriptPath '"'
cmd .= ' ' argument
result := MsgBox("是否创建开机启动项？(3秒后跳过)", , "YesNo T3")
if (result = "Yes") {
    FileCreateShortcut(A_ScriptDir '\embyToLocalPlayer_hide.ahk', A_Startup '\embyToLocalPlayer_hide_lnk.lnk', A_ScriptDir)
    Run('explorer shell:startup')
}
Run(cmd, , hideOrNot)