# qbittorrent\_webui\_open_file

需要 python。在 qBittorrent WebUI 里打开文件夹或者播放文件。

![](https://github.com/kjtsune/embyToLocalPlayer/raw/main/qbittorrent_webui_open_file/qbittorrent_webui_open_file.png)

**缺点**

* 本地需要安装 python
* 若种子含多文件，只播放体积最大的。
* 目前主要 windows 平台，其他尚未测试。
* mpv 用户一般还需要 AutoHotKey 用来激活 mpv 窗口，方便播放时直接使用键盘快捷键。如有其他方法麻烦告诉我，谢谢。

## 使用说明

> 基础配置

1. 下载 `embyToLocalPlayer.zip` 并解压到任意文件夹 [发布页](https://github.com/kjtsune/embyToLocalPlayer/releases)
2. 添加脚本匹配网址。油猴插件 > 已安装脚本 > 编辑 >
   设置。[发布页](https://greasyfork.org/zh-CN/scripts/450015-qbittorrent-webui-open-file?locale_override=1)
3. 安装 python (勾选 add to path) [官网](https://www.python.org/downloads/)
4. 配置 `embyToLocalPlayer.ini`

> [二选一] 简易模式 [推荐]

1. 下载解压并安装 AutoHotKey v2 [官网](https://www.autohotkey.com/) [链接](https://www.autohotkey.com/download/ahk-v2.zip)
2. 双击运行 `embyToLocalPlayer_debug.ahk`
3. 现在可网页播放测试，若正常，创建 `embyToLocalPlayer.ahk` 快捷方式，并放入开机启动文件夹即可。( `win + r` 输入 `shell:startup` 回车)
4. 删除 `active_video_player.exe`

> [二选一] 一般模式

1. 打开命令行。修改并输入 `python C:/<path_to>/embyToLocalPlayer.py`
2. 现在可网页播放测试，若正常，修改 `embyToLocalPlayer.vbs` 里的 python 路径和 `.py` 文件路径。
3. `.vbs` 放入开机启动文件夹即可 ( `win + r` 输入 `shell:startup` 回车)
4. 删除文件夹里所有 `.ahk` 的文件。
5. 若不喜欢 `active_video_player.exe` （不需要激活窗口功能可删） 且 mpv 没在前台启动。可自行配置 mpv `ontop = yes` ，或将 `portable_config`
   文件夹与 `mpv.exe` 放在一起。

> 其他

* 问题反馈群，提问前先尽量自行排查一下。[https://t.me/embyToLocalPlayer](https://t.me/embyToLocalPlayer)
