# embyToLocalPlayer-Python

需要 Python。若用 PotPlayer mpv IINA MPC VLC 播放，可回传播放进度。支持 Jellyfin Plex。

**缺点**

* 本地需要安装 Python
* 点击播放时会有未兼容流提示或转圈。 可另装 [脚本](https://greasyfork.org/zh-CN/scripts/448629-embyerrorwindows) 自动关闭。
* 问题反馈群，提问前先尽量自行排查一下。[https://t.me/embyToLocalPlayer](https://t.me/embyToLocalPlayer)

**特性**

* 在首页也可以播放。点击原来的播放按钮就可以。播放无需二次确认。
* 可回传播放进度到服务器。
* 视频文件 可本地 可挂载 可远端。（点击油猴插件有菜单）
* mpv MPC PotPlayer 通过网络播放时也支持外挂字幕。(播放前先选择字幕)
* 适配多视频版本，如 2160p 与 1080p 双文件的情况。(Plex 不支持)
* 其他播放器一般也能用，只是不会回传进度。
* （一般用不到）适配 弹弹play（动漫弹幕播放器）。（详见 FAQ）

**建议**

* emby 关联 Trakt，永久保存观看记录。跨平台，设备损坏可以导回来。（详见 FAQ）
* PotPlayer 播放 http 会疯狂写盘并把整个文件下载下来。推荐读取硬盘模式。
* 以下播放器支持回传进度。
    * PotPlayer [发布页](https://potplayer.daum.net/)
      若非读取硬盘播放，**可能提示地址关闭**， 解决方法在 FAQ。
    * mpv（纯快捷键）[Windows](https://sourceforge.net/projects/mpv-player-windows/files/release/) 。 macOS
      解压后拖到应用程序即可 [macOS](https://laboratory.stolendata.net/~djinn/mpv_osx/)
    * IINA（macOS）[发布页](https://iina.io/) 非读盘模式不支持外挂字幕文件（mpv 支持）
    * mpv.net（可鼠标）[发布页](https://github.com/stax76/mpv.net/releases)   
      **mpv 若无报错但播放失败，换 mpv.net 测试下** 。
    * VLC [发布页](https://www.videolan.org/vlc/)
    * MPC-HC [发布页](https://github.com/clsid2/mpc-hc/releases)
    * MPC-BE [发布页](https://sourceforge.net/projects/mpcbe/files/MPC-BE/Release%20builds/)

## 使用说明

> 基础配置

1. 下载 `embyToLocalPlayer.zip` 并解压到任意文件夹。 [发布页](https://github.com/kjtsune/embyToLocalPlayer/releases)
   ｜ [加速链接](https://github.ixiaocai.net/https://github.com/kjtsune/embyToLocalPlayer/releases/latest/download/embyToLocalPlayer.zip)
   （感谢）
2. 安装油猴脚本。 [发布页](https://greasyfork.org/zh-CN/scripts/448648-embytolocalplayer)
3. 安装 Python (勾选 add to path) [官网](https://www.python.org/downloads/)
4. 填写播放器路径与名称 `embyToLocalPlayer_config.ini`

> 前置说明

* 播放结束播放器要退出。
* 报错就截图发群里。 [可选] 自动关闭未兼容流提示详见 FAQ。
* [可选] 持久性缓存（边下边播）详见 FAQ。
* 若用 MPC 播放：开启 WebUI，详见 FAQ。

> Windows

* 双击 `embyToLocalPlayer_debug.bat`
* 按 1（窗口运行），若无报错，可网页播放测试。
* 按 2 则创建开机启动项并后台运行。

> macOS

1. 刚才保存的文件夹 > 右击 > 新建位于文件夹的终端窗口   `chmod chmod +x *.command` 回车。
2. 双击 `emby_script_run.command`, 若无报错，可播放测试。
3. 开机自启（无窗口运行）：
    1. 启动台 > 自动操作 > 文件 > 新建 > 应用程序 > 运行 Shell 脚本 >   
       把 `emby_script_run.command` 文件拖入 > 点击运行后测试播放 > 文件 > 存储 > 取名并保存到应用程序。
    2. 启动台 > 刚才的应用 > 双击后台运行后再次播放测试。
    3. 系统偏好设置 > 用户与群组 > 登录项 > 添加刚才的应用。

> Linux

1. 添加 `emby_script_run.command` 执行权限，并用终端打开。
2. 正常播放后，加入开机启动项（无窗口运行）：  
   Debian_Xfce：设置 > 会话和启动 > 应用程序自启动

## FAQ

> 通用说明

* [embyErrorWindows.js](https://greasyfork.org/zh-CN/scripts/448629-embyerrorwindows)
  可自动关闭 Emby 没有兼容流的窗口 和 Jellyfin 转圈提示。~~Plex 回放错误通过自动刷新页面解决。~~
* 同服务器同时开启多个浏览器标签页，会造成回传进度失败假象。手动刷新一下页面，或者只开一个标签。
* Windows：若 mpv 运行失败，换 mpv.net 试试看。或者 mpv release 0.34.0 版本。
* 问题反馈群，提问前先尽量自行排查一下。[https://t.me/embyToLocalPlayer](https://t.me/embyToLocalPlayer)

> 如何切换模式

* 点击浏览器油猴插件图标，会有菜单。
* 网页播放模式：开启 > 禁用脚本。
* 读取硬盘模式：关闭 > 调用本地播放器但使用服务器网络链接。（默认）
* 读取硬盘模式：开启 > 调用本地播放器并转换服务器路径为本地文件地址。（需要 `.ini` 里填好路径替换规则，服务端在本地则不用填）

> 如何更新

* 除了 `embyToLocalPlayer_config.ini`，其他全删除。再次去 github 下载解压当前文件夹，注意跳过 `.ini`。  
  同时看看 [embyToLocalPlayer_config.ini](https://github.com/kjtsune/embyToLocalPlayer/blob/main/embyToLocalPlayer_config.ini)
  有没有新内容。

> 持久性缓存（边下边播）相关

* 在 `.ini` 文件里 `gui` 部分设置启用。

* 如果播放进度超过下载进度，部分播放器会卡死。（Win：mpv 会，Pot 不会，其他没测）
* Windows 硬盘文件系统 NTFS 会造成额外磁盘开销和初始化下载慢，ReFS 正常。  
  因为视频文件需要先下载首尾部分才能播放。  
  解决方案：
    1. 下载时候选择 `顺序下载`（需要下载完毕才会用缓存播放，点播放会回退到网络播放模式）
    2. Win10 工作站版和企业版 支持 ReFS，把缓存盘格式化为 ReFS（数据会清空）。  
       开虚拟机或别的电脑装工作站版，然后直通硬盘并格式化成 ReFS 给 Win10 Pro 用。  
       Win8.1 有人改注册表支持。
    3. Linux ext4 通过 SMB 分享给 Windows
* 网页点击播放时弹出菜单：
    1. 播放：当缓存进度大于播放开始时间时用缓存播放。其他情况回退网络模式。
    2. 下载 1% 后播放：等待下载首尾各 1% 后启动播放器。其他等同于播放。
    3. 下载（首尾优先）：优先下载首尾各 1% ，可边下边播。
    4. 下载（顺序下载）：不能边下边播。
    5. 删除当前下载
    6. 下载管理器

> 字幕相关

* emby 里字幕选择无效。  
  外挂字幕选择有效，内置字幕会被忽略，由播放器选择。  
  视频文件的内置字幕当作外挂字幕处理会导致播放器语言设置失效。（外挂字幕最优先）  
  正常播放器都可以设置语言优先顺序。

> mpv 相关

* Windows：手动切换音轨字幕经常会卡死，偶尔启动时间会久，不知为何。~~mpv.net 好像不会~~）
* [可选] [portable_config](https://github.com/kjtsune/embyToLocalPlayer/tree/main/portable_config)
  文件夹是我用的 mpv 配置，可将整个文件夹与 `mpv.exe` 放在一起。
* 快捷键看 `input.conf`
* 其他设置 `mpv.conf`

> mpv.net 相关

* 设置播放完自动关闭。不加载下个文件。（触发回传进度）  
  右击 > Settings > Playback > idle:no, auto-load-folder:no （大概是这样
* bug: 影响很小。如果 save-position-on-quit = yes 会导致开始播放时间由播放器强制保存，原版 mpv 没这问题。

> PotPlayer 相关

* 若非读取硬盘播放，可能提示地址关闭  
  220914-64bit.exe + Win10 没问题。   
  Win8 32bit 碰到。解决方法是使用 [Portable](https://www.videohelp.com/software/PotPlayer/old-versions) 版本。  
  先打开 `PotPlayerPortable.exe` 一次，但播放用 `C:\<path_to>\PotPlayerPortable\App\PotPlayer\PotPlayer.exe`  
  不然会要求管理员权限运行。
* 选项 > 播放 > 播放窗口尺寸：全屏
* 配置/语言/其他 > 收尾处理 > 播放完当前后退出（触发回传进度）

> IINA 相关

* 退出播放器才会回传进度。
* 非读盘模式不支持外挂字幕文件（mpv 支持）

> MPC 相关：开启 WebUI

* 查看 > 选项 > Web 界面：  
  打勾 监听端口：13579  
  打勾 仅允许从 localhost 访问

> Trakt 相关

* 这是我自用的配置，可根据自己需求。我只用来记录观看记录，其他都不用。
* 插件 > 目录 > Trakt > 安装。
* 插件 > Trakt > Get PIN > 仅选中：Skip unwatched import from Trakt。其他取消。> 保存。
* 计划任务 > Sync library to trakt.tv > 删除。(可能首次使用 Trakt 的用户需要，把存在 Emby 的记录都传上去，我不确定，欢迎测试后告诉我。)
* 计划任务 > Import playstates from Trakt.tv > 开启。（设备迁移，或多平台，从 Trakt 导入播放记录）
* 可能有豆瓣迁移 Trakt 的脚本。
  ~~或者用 [linkDoubanTrakt](https://greasyfork.org/zh-CN/scripts/449899-linkdoubantrakt) 一个一个点。~~

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

* 若自动下一集则只回传上一集记录。
* 若通过 http 播放，有以下缺点：
    1. 每次播放需要选择弹幕。（已把文件名发送给播放器匹配）
    2. 启动时无法及时跳转到 emby 开始时间，需要播放开始后等待15秒。（每次看完一集则不影响）
    3. 无法加载外挂字幕。

**其他相关脚本**

* [embyDouban](https://greasyfork.org/zh-CN/scripts/449894-embydouban)
  ：豆瓣评分，链接，评论
* [linkDoubanTrakt](https://greasyfork.org/zh-CN/scripts/449899-linkdoubantrakt)
  ：Douban Trakt 互相跳转链接
* [qbittorrent\_webui\_open_file](https://greasyfork.org/zh-CN/scripts/450015-qbittorrent-webui-open-file)
  ：联动脚本，配置相同，QB 网页打开文件夹或播放
* [embyErrorWindows.js](https://greasyfork.org/zh-CN/scripts/448629-embyerrorwindows)
  ：自动关闭 Emby 没有兼容流的窗口 和 Jellyfin 转圈提示。~~Plex 回放错误通过自动刷新页面解决。~~

**感谢**

* [iwalton3/python-mpv-jsonipc](https://github.com/iwalton3/python-mpv-jsonipc)