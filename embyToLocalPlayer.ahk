#Requires AutoHotkey v2.0-beta
::1'3df,v\dip`'btw::by the way
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
CopySelfToDebugAndNot() {
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
        FileCopy(A_ScriptFullPath, name '.' fileType, true)
        FileCopy(A_ScriptFullPath, name '_debug.' fileType, true)
        Exit()
    }

}
CopySelfToDebugAndNot()
hideOrNot := InStr(A_ScriptFullPath, '_debug') ? '' : 'hide'
argument := ArgsArrayToString(A_Args)
pythonScriptPath := StrReplace(A_ScriptFullPath, '_debug', '')
pythonScriptPath := RegExReplace(pythonScriptPath, '(exe|ahk)$', 'py')
cmd := 'python ' pythonScriptPath
cmd .= ' ' argument
Run(cmd, , hideOrNot)