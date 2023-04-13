# qbittorrent\_webui\_open_file

需要 python。在 qBittorrent WebUI 里打开文件夹或者播放文件。

![](https://github.com/kjtsune/embyToLocalPlayer/raw/main/qbittorrent_webui_open_file/qbittorrent_webui_open_file.png)

**缺点**

* 本地需要安装 python
* 若种子含多文件，只播放体积最大的。

## 使用说明

**本脚本附属于 [embyToLocalPlayer](https://greasyfork.org/zh-CN/scripts/448648-embytolocalplayer)
，教程通用，有时候那边会更准确一点。有疑问可以参考那边。**


> 基础配置

1. 下载 `embyToLocalPlayer.zip` 并解压到任意文件夹 [发布页](https://github.com/kjtsune/embyToLocalPlayer/releases)
2. 添加脚本匹配网址。油猴插件 > 已安装脚本 > 编辑 >
   设置。[发布页](https://greasyfork.org/zh-CN/scripts/450015-qbittorrent-webui-open-file)
3. 安装 python (勾选 add to path) [官网](https://www.python.org/downloads/)
4. 填写播放器路径与名称以及路径转换规则 `embyToLocalPlayer_config.ini`

> Windows

* 双击 `embyToLocalPlayer_debug.bat`
* 按 1（窗口运行），若无报错，可网页播放测试。
* 按 2 则创建开机启动项并后台运行。
* 以下可选：
    * 命令行输入 `python -V` 检查 Python 是否安装成功。  
      Windows 11 有可能需要用商店安装。
    * 若自启失败，检查启动项是否被禁用：任务管理器 > 启动。
    * 若需要源码运行：安装 AutoHotKey v2 或把 `autohotkey_tool.ahk` 编译为 `exe`。
    * ~~告诉我怎么可以取消 AutoHotKey 依赖~~。即：通过 `.vbs` 自启后所有播放器都可以正常显示并激活。例如：mpv。

> macOS

1. 刚才保存的文件夹 > 右击 > 新建位于文件夹的终端窗口 `chmod +x *.command` 回车。
2. 双击 `emby_script_run.command`, 若无报错，可播放测试。
3. 开机自启（无窗口运行）：
    1. 启动台 > 自动操作 > 文件 > 新建 > 应用程序 > 运行 Shell 脚本 >   
       把 `emby_script_run.command` 文件拖入 > 点击运行后测试播放 > 文件 > 存储 > 取名并保存到应用程序。
    2. 启动台 > 刚才的应用 > 双击后台运行后再次播放测试。
    3. 系统偏好设置 > 用户与群组 > 登录项 > 添加刚才的应用。

> Linux

1. `apt install python3-tk`（没报错不装也行）
2. 添加 `emby_script_run.command` 执行权限，并用终端打开。
3. 正常播放后，加入开机启动项（无窗口运行）：  
   Debian_Xfce：设置 > 会话和启动 > 应用程序自启动