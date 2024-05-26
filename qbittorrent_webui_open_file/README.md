# qbittorrent\_webui\_open_file

在 qBittorrent WebUI 里打开文件夹或者播放文件。

![](https://github.com/kjtsune/embyToLocalPlayer/raw/main/qbittorrent_webui_open_file/qbittorrent_webui_open_file.png)

**缺点**

* 若种子含多文件，只播放体积最大的。

## 使用说明

**本脚本附属于 [embyToLocalPlayer](https://github.com/kjtsune/embyToLocalPlayer)
，教程通用，有时候那边会更准确一点。有疑问可以参考那边。**


> 基础配置

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

> 如何运行 Windows / macOS / Linux

* 按 [**embyToLocalPlayer**](https://github.com/kjtsune/embyToLocalPlayer) 原项目运行即可

> [可选] 使用网络播放（无需路径转换）

* 播放时，先检查本地挂载盘文件是否存在。若不存在，使用局域网 http 服务器链接播放。
* 文件所在的服务器也需要运行 embyToLocalPlayer
* 不支持外挂字幕。
* 填写位置：`.ini` > `[dev]`
  ```
    # 是否监听局域网，播放的播放端填 no（不然会无法使用），服务端填 yes。
    listen_on_lan = no
  
    # 可以填一个随机密码，保持服务端和客户端密码一致即可。
    http_server_token = etlp
   
    # 服务端的监听地址，默认会自动使用 qB WebUi 网址，所以一般留空即可。例如：http://192.168.2.111:58000
    server_side_href = 
  ```


