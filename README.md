# embyToLocalPlayer-Python

* Emby 调用 PotPlayer mpv IINA MPC VLC 播放，并回传播放进度（可关）。适配 Jellyfin Plex。
* 支持：纯本地｜网络｜持久性缓存｜下载 多种模式。
* 本地需要安装 Python

**特性**

* 在首页也可以播放。点击原来的播放按钮就可以。播放无需二次确认。
* 可持久性缓存文件到本地或预读取下一集。（网盘用户及 Emby 是别人分享的可能用到）
* 视频文件 可本地 可挂载 可远端。
* mpv VLC MPC PotPlayer 通过网络播放时也支持外挂字幕。(播放前先选择字幕)
* 其他播放器一般也能用，只是不会回传进度。

**以下播放器支持回传进度**

* PotPlayer [发布页](https://potplayer.daum.net/)
  若使用 http 播放，**可能提示地址关闭**， 解决方法在 FAQ。
* mpv（纯快捷键）[Windows](https://sourceforge.net/projects/mpv-player-windows/files/release/) 。 macOS
  解压后拖到应用程序即可 [macOS](https://laboratory.stolendata.net/~djinn/mpv_osx/)
* mpv.net（可鼠标）[发布页](https://github.com/stax76/mpv.net/releases)
* VLC [发布页](https://www.videolan.org/vlc/)
* MPC-HC [发布页](https://github.com/clsid2/mpc-hc/releases)
* MPC-BE [发布页](https://sourceforge.net/projects/mpcbe/files/MPC-BE/Release%20builds/)
* IINA（macOS）[发布页](https://iina.io/) 若使用 http 播放不支持外挂字幕文件（mpv 支持）

## 使用说明

### 基础配置

1. 下载 `embyToLocalPlayer.zip` 并解压到任意文件夹。 [发布页](https://github.com/kjtsune/embyToLocalPlayer/releases)
   ｜ [加速链接](https://github.ixiaocai.net/https://github.com/kjtsune/embyToLocalPlayer/releases/latest/download/embyToLocalPlayer.zip)
   （感谢）
2. 安装油猴脚本。 [发布页](https://greasyfork.org/zh-CN/scripts/448648-embytolocalplayer)
3. 安装 Python (勾选 add to path) [官网](https://www.python.org/downloads/)
4. 填写播放器路径与名称 `embyToLocalPlayer_config.ini`

### 前置说明

* 网页闪一下是自动关闭兼容流提示。
* 播放器要退出触发回传进度。
* 报错就截图发群里。见 FAQ。

### Windows

* 双击 `embyToLocalPlayer_debug.bat`
* 按 1（窗口运行），若无报错，可网页播放测试。
* 按 2 则创建开机启动项并后台运行。

### macOS

1. 刚才保存的文件夹 > 右击 > 新建位于文件夹的终端窗口 `chmod +x *.command` 回车。
2. 双击 `emby_script_run.command`, 若无报错，可播放测试。
3. 开机自启（无窗口运行）：
    1. 启动台 > 自动操作 > 文件 > 新建 > 应用程序 > 运行 Shell 脚本 >   
       把 `emby_script_run.command` 文件拖入 > 点击运行后测试播放 > 文件 > 存储 > 取名并保存到应用程序。
    2. 启动台 > 刚才的应用 > 双击后台运行后再次播放测试。
    3. 系统偏好设置 > 用户与群组 > 登录项 > 添加刚才的应用。

### Linux

1. `apt install python3-tk`（没报错不装也行）
2. 添加 `emby_script_run.command` 执行权限，并用终端打开。
3. 正常播放后，加入开机启动项（无窗口运行）：  
   Debian_Xfce：设置 > 会话和启动 > 应用程序自启动

## FAQ

### 通用说明

* 用鼠标手势软件关闭播放器体验更舒服一点。
* 同服务器同时开启多个浏览器标签页，会造成回传进度失败假象。手动刷新一下页面，或者只开一个标签。
* 非本地用户：Plex 及部分域名有 dns 污染，若无法播放，系统 dns 改成 `223.5.5.5 119.29.29.29` 后重启电脑再尝试。
* Windows：若自启失败，检查启动项是否被禁用：任务管理器 > 启动
* Windows：若源码运行：安装 AutoHotKey v2 或把 `autohotkey_tool.ahk` 编译为 `exe`。
* 反馈群组在频道置顶，提问前先把 FAQ 看一遍，不含敏感数据不私聊。  
  小更新会频道提醒，不过应该也没什么更新的了，反馈不需要关注频道。[https://t.me/embyToLocalPlayer](https://t.me/embyToLocalPlayer)

### 如何切换模式

* 点击浏览器油猴插件图标，会有菜单。
* 网页播放模式：开启 > 禁用脚本。
* 读取硬盘模式：关闭 > 调用本地播放器但使用服务器网络链接。（默认）
* 读取硬盘模式：开启 > 调用本地播放器并转换服务器路径为本地文件地址。（需要 `.ini` 里填好路径替换规则，服务端在本地则不用填）
* 持久性缓存模式：只看配置文件，与油猴设置不冲突，不需要开启读取硬盘模式。

### 如何更新

* 将 `_config.ini` 重命名为 `.ini`，其他全删除。再次 GitHub 下载解压当前文件夹。（`.ini` 优先于 `_config.ini`  ）
* 同时看看 `embyToLocalPlayer_config.ini` 有没有新内容。
* 油猴脚本也记得要更新。

### 如何反馈

* 脚本报错，提供报错截图。
* 脚本若无报错，提供以下信息：
    1. 换播放器及换视频文件测试是否复现
    2. 系统名称
    3. 无歧义播放器名称 (原版 mpv 等 ... )
    5. 什么模式播放
    6. 怎么复现（完整点会比较好）
    7. 运行日志（没有也可以，有更好）
    
### 字幕相关

* Emby 里字幕选择无效。  
  外挂字幕选择有效，内置字幕会被忽略，由播放器选择。  
  视频文件的内置字幕当作外挂字幕处理会导致播放器语言设置失效。（外挂字幕最优先）  
  正常播放器都可以设置语言优先顺序。

### mpv 相关

* [可选] [portable_config](https://github.com/kjtsune/embyToLocalPlayer/tree/main/portable_config)
  文件夹是我用的 mpv 配置，可将整个文件夹与 `mpv.exe` 放在一起。
* 快捷键看 `input.conf`
* 其他设置 `mpv.conf`

### mpv.net 相关

* 设置播放完自动关闭。不加载下个文件。（触发回传进度）  
  右击 > Settings > Playback > idle:no, auto-load-folder:no （大概是这样
* bug: 影响很小。如果 save-position-on-quit = yes 会导致开始播放时间由播放器强制保存，原版 mpv 没这问题。

### PotPlayer 相关

* 若使用 http 播放，可能提示地址关闭  
  220914-64bit.exe + Win10 没问题。   
  Win8 32bit 碰到。解决方法是使用 [Portable](https://www.videohelp.com/software/PotPlayer/old-versions) 版本。  
  先打开 `PotPlayerPortable.exe` 一次，但播放用 `C:\<path_to>\PotPlayerPortable\App\PotPlayer\PotPlayer.exe`  
  不然会要求管理员权限运行。
* 选项 > 播放 > 播放窗口尺寸：全屏
* 配置/语言/其他 > 收尾处理 > 播放完当前后退出（触发回传进度）

### MPC 相关：

* 会自动开启 WebUI 建议仅允许从 localhost 访问： 查看 > 选项 > Web 界面：  
  打勾 仅允许从 localhost 访问

### IINA 相关

* 退出播放器才会回传进度。
* 非读盘模式不支持外挂字幕文件（mpv 支持）

### Jellyfin 相关

* 首页播放结束后，10秒内重复播放**同文件**，本地播放器收到的播放时间会有误。    
  解决方法：
    1. 进详情后再播放没这问题；~~说明不是我的锅~~
    2. 等待10秒后再继续播放；
    3. 手动刷新页面后播放；
    4. ~~告诉我要发送什么请求可以解决这个问题~~

### 播放列表相关

* 在配置文件里 `[playlist]` 中启用
* 可能与缓存模式冲突
* 播放列表添加完成前最好不退出
* Plex 未适配

**Windows:**

* mpv:
* mpv.net:
* vlc:
* mpc: be: 播放列表条目超过10个可能会卡住，hc 没这问题。
* pot: 下一集无法添加外挂字幕。

**macOS**

* mpv:
* iina: 仅读盘模式支持并可回传
* vlc: 下一集无法添加外挂字幕。

**Linux**

* mpv:
* vlc: 下一集无法添加外挂字幕。

### 持久性缓存（边下边播）相关

* 在配置文件里 `[gui]` 中启用
* 如果播放进度超过下载进度，建议关闭播放器触发回传以保存播放进度。（以下为 Windows 平台测试）：   
  mpv mpv.net 会停止播放十几秒。  
  Pot 会停止播放或跳到尾部。(记得拖回来再关闭）  
  MPC 会退出播放器。  
  VLC 会停止播放。
* Windows：（ Linux ext4, macOS APFS 没问题。）   
  问题：默认的硬盘文件系统 NTFS 会造成额外磁盘开销和初始化时间久，ReFS 正常。  
  解决方案：
    1. 使用 `顺序下载`（需要下载完毕才会用缓存播放，点播放会回退到网络播放模式）
    2. Win10 工作站版和企业版 支持 ReFS，把缓存盘或分区格式化为 ReFS（数据会清空）。
    3. 未核实：用密匙升级为工作站版，或下载镜像重新安装（选保留数据）。
    4. 开虚拟机或别的电脑有工作站版，然后直通硬盘并格式化成 ReFS 给 Win10 用（专业版测试可行）。  
       Win8.1 有人改注册表支持。
    5. Linux ext4 通过 SMB 分享给 Windows
* 网页点击播放时弹出菜单：
    1. 播放：当缓存进度大于播放开始时间时用缓存播放。其他情况回退网络模式。
    2. 下载 1% 后播放：等待下载首尾各 1% 后启动播放器。其他等同于播放。
    3. 下载（首尾优先）：优先下载首尾各 1% ，可边下边播。
    4. 下载（顺序下载）：不能边下边播。
    5. 删除当前下载
    6. 下载管理器

### Plex 相关

* 可能 dns 污染，若无法播放。系统 dns 改成 `223.5.5.5 119.29.29.29` 后重启电脑再尝试。
* PotPlayer  
  播放 http 时无法读取外挂字幕，读取硬盘模式却可以。（字幕手动上传的，本地硬盘没有，比较玄学）
* 会提示回放错误，随便点一下就会消失。

### 弹弹play 相关

* 若通过 http 播放，有以下缺点：
    1. 每次播放需要选择弹幕。（已把文件名发送给播放器匹配）
    2. 启动时无法及时跳转到 Emby 开始时间，需要播放开始后等待15秒。（每次看完一集则不影响）
    3. 无法加载外挂字幕。

### 其他脚本

* [embyDouban](https://greasyfork.org/zh-CN/scripts/449894-embydouban)
  ：豆瓣评分，链接，评论
* [linkDoubanTrakt](https://greasyfork.org/zh-CN/scripts/449899-linkdoubantrakt)
  ：Douban Trakt 互相跳转链接
* [qbittorrent\_webui\_open_file](https://greasyfork.org/zh-CN/scripts/450015-qbittorrent-webui-open-file)
  ：联动脚本，配置相同，QB 网页打开文件夹或播放
* [ccf-2012/torcp](https://github.com/ccf-2012/torcp)
  : 适合 pt。将视频硬链接并重命名为 Emby 能识别的命名方式。

### 感谢

* [iwalton3/python-mpv-jsonipc](https://github.com/iwalton3/python-mpv-jsonipc)