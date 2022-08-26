# embyToLocalPlayer

需要 python。若用 mpv 播放，可更新服务器观看进度。

**另外推荐**

* qbittorrent\_webui\_open_file (
  联动脚本，配置相同) [GreasyFork](https://greasyfork.org/zh-CN/scripts/450015-qbittorrent-webui-open-file?locale_override=1)
* embyDouban [GreasyFork](https://greasyfork.org/zh-CN/scripts/449894-embydouban?locale_override=1)
* Jellyfin MPV Shim [Github](https://github.com/jellyfin/jellyfin-mpv-shim)  
  这个可以连接emby，只是每次打开浏览器需要点一下右上角的“播放到”按钮。  
  开发比较成熟。体验更好。

**缺点**

* 本地需要安装 python
* 目前主要 windows 平台，其他尚未测试。
* 会提示没有兼容的流，可另装脚本自动关闭提示。
* 一般还需要 AutoHotKey 用来激活 mpv 窗口，方便播放时直接使用键盘快捷键。如有其他方法麻烦告诉我，谢谢。

**特性**

* 在首页也可以播放。点击原来的播放按钮就可以。不改变页面布局。
* 可回传播放进度到服务器。若需要此功能，配置文件里填 mpv 的播放器。
* 文件本地或挂载或远端均可。（脚本菜单里选择）
* mpv potplayer mpc 支持服务端的外挂字幕。(播放前先选择字幕)
* 不影响其他功能使用。
* 适配多视频版本，如 2160p 与 1080p 双文件的情况。

**建议**

* 最佳体验请用 mpv ，嫌配置麻烦可以用 mpv.net 或我的配置文件。
* potplayer 播放 http 会疯狂写盘并把整个文件下载下来。非挂载不建议使用。

## 使用说明

> 基础配置

1. 下载 `embyToLocalPlayer.zip` 并解压到任意文件夹 [发布页](https://github.com/kjtsune/embyToLocalPlayer/releases)
2. (可选) 添加脚本匹配网址。油猴插件 > 已安装脚本 > 编辑 >
   设置。 [发布页](https://greasyfork.org/zh-CN/scripts/448648-embytolocalplayer?locale_override=1)
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

> 可选操作

* 安装 `embyErrorWindows.js`
  可自动关闭提示没有兼容流的窗口。[发布页](https://greasyfork.org/zh-CN/scripts/448629-embyerrorwindows?locale_override=1)
* `portable_config` 文件夹是我的 mpv 配置，可下载绿色版 mpv 将其与 `mpv.exe` 放在一起。
* 问题反馈群，提问前先尽量自行排查一下。[https://t.me/embyToLocalPlayer](https://t.me/embyToLocalPlayer)

**感谢**

* [iwalton3/python-mpv-jsonipc](https://github.com/iwalton3/python-mpv-jsonipc)