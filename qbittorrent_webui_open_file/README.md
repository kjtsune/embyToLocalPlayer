# qbittorrent\_webui\_open_file

在 qBittorrent WebUI 里打开文件夹或者播放文件。

![](https://github.com/kjtsune/embyToLocalPlayer/raw/main/qbittorrent_webui_open_file/qbittorrent_webui_open_file.png)

**缺点**

* 若种子含多文件，只播放体积最大的。

## 使用说明

**本脚本附属于 [embyToLocalPlayer](https://greasyfork.org/zh-CN/scripts/448648-embytolocalplayer)
，教程通用，有时候那边会更准确一点。有疑问可以参考那边。**


> 基础配置 > 按 **embyToLocalPlayer** 原项目配置即可

1. 下载 `etlp-python-embed-win32.zip` (**便携版** | Windows only)   
   或者 `etlp-mpv-py-embed-win32.zip` (含mpv播放器便携版 | Windows only | 快捷键见 FAQ)  
   或者 `embyToLocalPlayer.zip` (Windows / Linux / macOS)  
   然后解压到任意文件夹。 [发布页](https://github.com/kjtsune/embyToLocalPlayer/releases)
2. 进入文件夹，修改配置文件：`embyToLocalPlayer_config.ini` 中的播放器路径，以及播放器选择。（若使用含mpv便携版，则无需配置。）
3. 安装 Python (勾选 add to path) [官网](https://www.python.org/downloads/)
   （若使用便携版，则无需安装。）

> **差异配置 （特别注意）**

* 添加本油猴脚本匹配网址：油猴插件 > 已安装脚本 > `qbittorrent_webui_open_file` > 编辑 >
  设置 > 用户匹配 > 添加 > 填入 qBittorrent WebUi
  的网址。[发布页](https://greasyfork.org/zh-CN/scripts/450015-qbittorrent-webui-open-file)
* 进入文件夹，修改配置文件：`embyToLocalPlayer_config.ini` 中的路径转换规则。

> 如何运行 Windows / macOS / Linux > 按 **embyToLocalPlayer** 原项目运行即可

