#Requires AutoHotkey v2.0-beta

MsgBox("
(
embyToLocalPlayer.ahk 已废弃。
_debug.bat 可以创建开机启动项了。
旧的启动项，弹出启动文件夹后手动删除。
.ini也改名为_config.ini。但不强制。
)")
Run('explorer shell:startup')