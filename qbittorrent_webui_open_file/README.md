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
4. 填写播放器路径与名称以及路径转换规则 `embyToLocalPlayer_config.ini`

> Windows

* 双击 `embyToLocalPlayer_debug.bat`
* 按 1（窗口运行），若无报错，可网页播放测试。
* 按 2 则创建开机启动项并后台运行。

> 其他

* 问题反馈群，提问前先尽量自行排查一下。[https://t.me/embyToLocalPlayer](https://t.me/embyToLocalPlayer)
