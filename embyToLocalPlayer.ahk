#Requires AutoHotkey v2.0-beta

MsgBox("
(
embyToLocalPlayer.ahk 已改名
新名称：embyToLocalPlayer_hide.ahk。
请运行_debug.ahk 添加新启动项。
旧的启动项，弹出启动文件夹后手动删除。
.ini也改名为_config.ini。目前都兼容。
)")
Run('explorer shell:startup')