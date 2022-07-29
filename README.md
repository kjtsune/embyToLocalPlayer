# embyToLocalPlayer

需要python和挂载硬盘。若用mpv播放，可更新服务器观看进度。

**缺点**

* 文件在本地或者挂载为本地硬盘
* 本地需要安装python
* 会提示没有兼容的流，可另装脚本自动关闭提示。

**优点**

* 在首页也可以播放。点击原来的播放按钮就可以。不改变页面布局。
* 可回传播放进度到服务器。若需要此功能，配置文件里填mpv的播放器。
* 不影响其他功能使用。

## 使用说明

> 基础配置

1. 下载embyToLocalPlayer.zip并解压到任意文件夹 [链接](https://github.com/kjtsune/embyToLocalPlayer/releases)
2. 安装tampermonkey [官网](https://www.tampermonkey.net/)
3. 安装并修改或添加匹配网址embyToLocalPlayer.js [发布页]
4. 安装python [官网](https://www.python.org/downloads/)
5. 配置embyToLocalPlayer.ini

> [二选一] 简易模式 [推荐]

6. 下载解压并安装 AutoHotKey [官网](https://www.autohotkey.com/download/ahk-v2.zip)
7. 双击运行 embyToLocalPlayer_debug.ahk
8. 现在可网页播放测试，若正常，创建embyToLocalPlayer.ahk快捷方式，并放入开机启动文件夹即可。(`win + r` 输入 `shell:startup` 回车)

> [二选一] 一般模式

9. 打开命令行。修改并输入 `python C:/path/to/embyToLocalPlayer.py`
10. 现在可网页播放测试，若正常，修改embyToLocalPlayer.vbs里的python路径和.py文件路径。
11. .vbs放入开始文件夹即可 (`win + r` 输入 `shell:startup` 回车)
12. 删除文件夹里所有.ahk的文件。

> 可选操作

* 安装embyErrorWindows.js 可自动关闭提示没有兼容流的窗口。[链接](https://greasyfork.org/en/scripts/448629-embyerrorwindows)
* active_video_player.ahk 是用来激活播放器。不然mpv播放后需要鼠标点击激活窗口才可以使用mpv键盘快捷键。需要[二选一]的简易模式。
