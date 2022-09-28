# qbittorrent\_webui\_open_file

需要 python。在 qBittorrent WebUI 里打开文件夹或者播放文件。

![](https://github.com/kjtsune/embyToLocalPlayer/raw/main/qbittorrent_webui_open_file/qbittorrent_webui_open_file.png)

**缺点**

* 本地需要安装 python
* 若种子含多文件，只播放体积最大的。
* 主要 windows 平台，其他尚未测试。

## 使用说明

**本脚本附属于 [embyToLocalPlayer](https://greasyfork.org/zh-CN/scripts/448648-embytolocalplayer?locale_override=1)
，教程通用，有时候那边会更准确一点。有疑问可以参考那边。**


> 基础配置

1. 下载 `embyToLocalPlayer.zip` 并解压到任意文件夹 [发布页](https://github.com/kjtsune/embyToLocalPlayer/releases)
2. 添加脚本匹配网址。油猴插件 > 已安装脚本 > 编辑 >
   设置。[发布页](https://greasyfork.org/zh-CN/scripts/450015-qbittorrent-webui-open-file?locale_override=1)
3. 安装 python (勾选 add to path) [官网](https://www.python.org/downloads/)
4. 填写播放器路径与名称以及路径转换规则 `embyToLocalPlayer.ini`

> [二选一] Windows 简易模式

1. 下载解压并点击 `Install.cmd` 安装 AutoHotKey
   v2 [官网](https://www.autohotkey.com/) [链接](https://www.autohotkey.com/download/ahk-v2.zip)
2. 双击 `embyToLocalPlayer_debug.bat` 或 `embyToLocalPlayer_debug.ahk`（窗口运行）。
3. 现在可网页播放测试，若正常，运行 `embyToLocalPlayer_debug.ahk` 创建开机启动项。
4. 双击 `embyToLocalPlayer.ahk`（无窗口运行）
5. 删除 `autohotkey_tool.exe`（不删也行）

> [二选一] Windows 一般模式

1. 双击 `embyToLocalPlayer_debug.bat`  若无报错可网页播放测试。  
   若正常，修改 `embyToLocalPlayer.vbs` 里的 Python 路径和 `.py` 文件路径。
2. 双击 `.vbs` 会（无窗口运行），再次测试播放。然后放入开机启动文件夹即可
3. 删除文件夹里所有 `.ahk` 的文件。（没报错不删也可以）
4. 若不需要激活窗口功能可删 `autohotkey_tool.exe` ，PotPlayer MPC 可能不需要。

> 其他

* 问题反馈群，提问前先尽量自行排查一下。[https://t.me/embyToLocalPlayer](https://t.me/embyToLocalPlayer)
