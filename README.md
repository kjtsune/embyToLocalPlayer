# embyToLocalPlayer-Python

需要 Python。若用 PotPlayer mpv IINA MPC VLC 播放，可回传播放进度。支持 Jellyfin Plex。

**缺点**

* 本地需要安装 Python
* 点击播放时会有未兼容流提示或转圈。 可另装 [脚本](https://greasyfork.org/zh-CN/scripts/448629-embyerrorwindows?locale_override=1) 自动关闭。
* 问题反馈群，提问前先尽量自行排查一下。[https://t.me/embyToLocalPlayer](https://t.me/embyToLocalPlayer)

**特性**

* 在首页也可以播放。点击原来的播放按钮就可以。播放无需二次确认。
* 可回传播放进度到服务器。
* 视频文件 可本地 可挂载 可远端。（点击油猴插件有菜单）
* mpv MPC PotPlayer 支持服务端的外挂字幕。(播放前先选择字幕)
* 适配多视频版本，如 2160p 与 1080p 双文件的情况。(Plex 不支持)
* 适配 弹弹play（动漫弹幕播放器），可回传。（详见 FAQ）

**建议**

* emby 关联 Trakt，在线永久保存观看记录。跨平台，设备损坏可以导回来。（详见 FAQ）
* PotPlayer 播放 http 会疯狂写盘并把整个文件下载下来。推荐读取硬盘模式。
* 使用以下 7 款播放器。
    * PotPlayer [发布页](https://potplayer.daum.net/)
      若非读取硬盘播放，**可能提示地址关闭**， 解决方法在 FAQ。
    * mpv（纯快捷键）[Windows](https://sourceforge.net/projects/mpv-player-windows/files/release/) 。 macOS
      解压后拖到应用程序即可 [macOS](https://laboratory.stolendata.net/~djinn/mpv_osx/)
    * IINA （macOS）[发布页](https://iina.io/) 非读盘模式不支持外挂字幕文件（mpv 支持）
    * mpv.net（可鼠标）[发布页](https://github.com/stax76/mpv.net/releases)   
      **mpv 若无报错但播放失败，换 mpv.net 测试下** 。
    * VLC [发布页](https://www.videolan.org/vlc/)
    * MPC-HC [发布页](https://github.com/clsid2/mpc-hc/releases)
    * MPC-BE [发布页](https://sourceforge.net/projects/mpcbe/files/MPC-BE/Release%20builds/)

## 使用说明

> 基础配置

1. 下载 `embyToLocalPlayer.zip` 并解压到任意文件夹 [发布页](https://github.com/kjtsune/embyToLocalPlayer/releases)
2. 安装油猴脚本。 [发布页](https://greasyfork.org/zh-CN/scripts/448648-embytolocalplayer?locale_override=1)
3. 安装 Python (勾选 add to path) [官网](https://www.python.org/downloads/)
4. 填写播放器路径与名称 `embyToLocalPlayer_config.ini`

> 如何试用

* 报错就截图发群里。
* Windows：双击 `embyToLocalPlayer_debug.bat`后按 1。若无报错，可播放测试。
* macOS：
    1. 刚才保存的文件夹 > 右击 > 新建位于文件夹的终端窗口 > `chmod +x emby_script_run.command` 回车。
    2. 双击 `emby_script_run.command`。 若无报错，可播放测试。
* Linux：双击运行`embyToLocalPlayer.py`，或终端运行。若无报错，可播放测试。
* IINA 播放完要退出。
* 若用 MPC 播放：开启 WebUI，详见 FAQ。

> Windows [二选一] 简易模式

1. 下载解压并点击 `Install.cmd` 安装 AutoHotKey
   v2 [官网](https://www.autohotkey.com/) [链接](https://www.autohotkey.com/download/ahk-v2.zip)
2. 双击 `embyToLocalPlayer_debug.bat` 或 `embyToLocalPlayer_debug.ahk`（窗口运行）。
3. 现在可网页播放测试，若正常，运行 `embyToLocalPlayer_debug.ahk` 创建开机启动项。
4. 双击 `embyToLocalPlayer_hide.ahk`（无窗口运行）
5. [可选] 删除 `autohotkey_tool.exe`

> Windows [二选一] 一般模式

1. 双击 `embyToLocalPlayer_debug.bat`  若无报错可网页播放测试。  
   若正常，修改 `embyToLocalPlayer.vbs` 里的 Python 路径和 `.py` 文件路径。
2. 双击 `.vbs` 会（无窗口运行），再次测试播放。然后放入开机启动文件夹即可
3. [可选] 删除文件夹里所有 `.ahk` 的文件。（若已删除 `autohotkey_tool.exe` 则为必选）
4. [可选] 若不需要激活窗口功能可删 `autohotkey_tool.exe` ，PotPlayer MPC 可能不需要。

> macOS

1. 刚才保存的文件夹 > 右击 > 新建位于文件夹的终端窗口 > `chmod +x emby_script_run.command` 回车。
2. 双击 `emby_script_run.command`, 若无报错，可播放测试。
3. 开机后台自启：
    1. 启动台 > 自动操作 > 文件 > 新建 > 应用程序 > 运行 Shell 脚本 >   
       把 `emby_script_run.command` 文件拖入 > 点击运行后测试播放 > 文件 > 存储 > 取名并保存到应用程序。
    2. 启动台 > 刚才的应用 > 双击后台运行后再次播放测试。
    3. 系统偏好设置 > 用户与群组 > 登录项 > 添加刚才的应用。

> Linux

1. 双击运行`embyToLocalPlayer.py`，或终端运行。
2. 正常播放后，用 `emby_script_tmux.command` 来开机启动。（还没测试）

> 其他操作

* [embyErrorWindows.js](https://greasyfork.org/zh-CN/scripts/448629-embyerrorwindows?locale_override=1)
  可自动关闭 Emby 没有兼容流的窗口 和 Jellyfin 转圈提示。~~Plex 回放错误通过自动刷新页面解决。~~
* 若 mpv 运行失败，换 mpv.net 试试看。或者 mpv release 0.34.0 版本。
* 问题反馈群，提问前先尽量自行排查一下。[https://t.me/embyToLocalPlayer](https://t.me/embyToLocalPlayer)

## FAQ

> 如何切换模式

* 点击浏览器油猴插件图标，会有菜单
* 网页播放模式：开启 > 禁用脚本。
* 读取硬盘模式：关闭 > 调用本地播放器但使用服务器网络链接。（默认）
* 读取硬盘模式：开启 > 调用本地播放器并转换服务器路径为本地文件地址。（需要 `.ini` 里填好路径替换规则，服务端在本地则不用填）

> 如何更新

* 除了 `embyToLocalPlayer_config.ini`，其他全删除。再次去 github 下载解压当前文件夹，注意跳过 `.ini`。  
  同时看看 [embyToLocalPlayer_config.ini](https://github.com/kjtsune/embyToLocalPlayer/blob/main/embyToLocalPlayer_config.ini)
  有没有新内容。
* 新功能或者修复之前比较重要的问题才会触发油猴更新提醒， github 会详细些。正常使用不更新也可以。  
  没什么问题应该也不怎么更新了

> Trakt 相关

* 这是为自用的配置，可根据自己需求。我只用来同步观看记录，其他都不用。
* 插件 > 目录 > Trakt > 安装。
* 插件 > Trakt > Get PIN > 仅选中：Skip unwatched import from Trakt。其他取消。> 保存。
* 计划任务 > Sync library to trakt.tv > 删除。(可能首次使用 Trakt 的用户需要，把存在 Emby 的记录都传上去，我不确定，欢迎测试后告诉我。)
* 计划任务 > Import playstates from Trakt.tv > 开启。（设备迁移，或多平台，从 Trakt 导入播放记录）
* 可能有豆瓣迁移 Trakt 的脚本。
  ~~或者用 [linkDoubanTrakt](https://greasyfork.org/zh-CN/scripts/449899-linkdoubantrakt?locale_override=1) 一个一个点。~~

> PotPlayer 相关

* 若非读取硬盘播放，可能提示地址关闭  
  220914-64bit.exe + Win10 没问题。   
  Win8 32bit 碰到。解决方法是使用 [Portable](https://www.videohelp.com/software/PotPlayer/old-versions) 版本。  
  先打开 `PotPlayerPortable.exe` 一次，但播放用 `C:\<path_to>\PotPlayerPortable\App\PotPlayer\PotPlayer.exe`  
  不然会要求管理员权限运行。
* 选项 > 播放 > 播放窗口尺寸：全屏
* 配置/语言/其他 > 收尾处理 > 播放完当前后退出（触发回传进度）

> 字幕相关

* 经常碰到播放器字幕不选择中文。   
  在电影详情页播放时，Emby 会自动选中一个字幕，我无法分辨字幕是你选的还是自动选的。故当作外挂字幕处理。 播放器一般会优先使用外挂字幕。
    1. Emby 设置 > 字幕 > 首选字幕语言：中文 ｜ 字幕模式：智能或关（若关则交由播放器自己判断内置字幕）
    2. 或者别进详情播放，这样子 Emby 也不会帮你选字幕。
    3. 播放器自己一般也可以配置字幕优先的语言。

> IINA 相关

* 退出播放器才会回传进度。
* 非读盘模式不支持外挂字幕文件（mpv 支持）

> MPC 相关：开启 WebUI

* 查看 > 选项 > Web 界面：  
  打勾 监听端口：13579  
  打勾 仅允许从 localhost 访问

> VLC 相关

* 优先中文字幕：  
  工具 > 偏好设置 > 字幕 > 首选字幕语言：`chi`

> mpv.net 相关

* 设置播放完自动关闭。不加载下个文件。（触发回传进度）
* 右击 > Settings > Playback > idle:no, auto-load-folder:no （大概是这样
* bug: 影响很小。如果 save-position-on-quit = yes 会导致开始播放时间由播放器强制保存，原版 mpv 没这问题。

> [可选] mpv 相关

* [portable_config](https://github.com/kjtsune/embyToLocalPlayer/tree/main/portable_config)
  文件夹是我用的 mpv 配置，可将整个文件夹与 `mpv.exe` 放在一起。
* 快捷键看 `input.conf`
* 其他设置 `mpv.conf`

> Jellyfin 相关

* 首页播放结束后，10秒内重复播放**同文件**，本地播放器收到的播放时间会有误。    
  解决方法：
    1. 进详情后再播放没这问题；~~说明不是我的锅~~
    2. 等待10秒后再继续播放；
    3. 手动刷新页面后播放；
    4. ~~告诉我要发送什么请求可以解决这个问题~~

> Plex 相关

* PotPlayer  
  播放 http 时无法读取外挂字幕，读取硬盘模式却可以。（字幕手动上传的，本地硬盘没有，比较玄学）
* 会提示回放错误，随便点一下就会消失。也可以安装下面脚本，通过自动刷新页面来解决。（比较粗暴）

> 弹弹play 相关

* 可回传播放记录。
* 读取硬盘模式体验会比较好。（若自动下一集则只回传上一集记录）
* 若通过 http 播放，有以下缺点：
    1. 每次播放需要选择弹幕。（已把文件名发送给播放器匹配）
    2. 启动时无法及时跳转到 emby 开始时间，需要播放开始后等待15秒。（每次看完一集则不影响）
    3. 无法加载外挂字幕。
* 以上缺点若有需求可以尝试反馈给 弹弹play 开发者 [Github](https://github.com/kaedei/dandanplay-libraryindex/issues) ：  
  因为我不知道是否有人需要这个功能。~~可能 emby 是别人分享来的用户需要。~~
    1. 请求命令行或专用链增加 fileHash 参数。
    2. 请求命令行或专用链增加 startTime 参数。
    3. 请求命令行或专用链增加 subFile 参数。（我们可以下载字幕到本地）

**其他相关脚本**

* [embyDouban](https://greasyfork.org/zh-CN/scripts/449894-embydouban?locale_override=1)
  ：豆瓣评分，链接，评论
* [linkDoubanTrakt](https://greasyfork.org/zh-CN/scripts/449899-linkdoubantrakt?locale_override=1)
  ：Douban Trakt 互相跳转链接
* [qbittorrent\_webui\_open_file](https://greasyfork.org/zh-CN/scripts/450015-qbittorrent-webui-open-file?locale_override=1)
  ：联动脚本，配置相同，QB 网页打开文件夹或播放
* [embyErrorWindows.js](https://greasyfork.org/zh-CN/scripts/448629-embyerrorwindows?locale_override=1)
  ：自动关闭 Emby 没有兼容流的窗口 和 Jellyfin 转圈提示。~~Plex 回放错误通过自动刷新页面解决。~~

**感谢**

* [iwalton3/python-mpv-jsonipc](https://github.com/iwalton3/python-mpv-jsonipc)