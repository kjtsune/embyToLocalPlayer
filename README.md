# embyToLocalPlayer-Python

* Emby 调用 PotPlayer mpv IINA MPC VLC 播放，并回传播放进度（可关）。适配 Jellyfin Plex。
* 支持：纯本地｜网络｜持久性缓存｜下载 多种模式。
* 本地需要安装 Python

**特性**

* 在首页也可以播放。点击原来的播放按钮就可以。播放无需二次确认。
* 可持久性缓存文件到本地。（网盘用户及 Emby 是别人分享的可能用到）
* 视频文件 可本地 可挂载 可远端。
* mpv VLC MPC PotPlayer 通过网络播放时也支持外挂字幕。(播放前先选择字幕)
* 其他播放器一般也能用，只是不会回传进度。

**以下播放器支持回传进度**

* PotPlayer [发布页](https://potplayer.daum.net/)
  若使用 http 播放，**可能提示地址关闭**， 解决方法在 FAQ。
* mpv（纯快捷键）[Windows](https://sourceforge.net/projects/mpv-player-windows/files/64bit/) 。 macOS
  解压后拖到应用程序即可 [macOS](https://laboratory.stolendata.net/~djinn/mpv_osx/)
* mpv.net（可鼠标）[发布页](https://github.com/stax76/mpv.net/releases)
* VLC [发布页](https://www.videolan.org/vlc/)
* MPC-HC [发布页](https://github.com/clsid2/mpc-hc/releases)
* MPC-BE [发布页](https://sourceforge.net/projects/mpcbe/files/MPC-BE/Release%20builds/)
* IINA（macOS）[发布页](https://iina.io/) 若使用 http 播放不支持外挂字幕文件（mpv 支持）

## 使用说明

> 基础配置

1. 下载 `embyToLocalPlayer.zip` 并解压到任意文件夹。 [发布页](https://github.com/kjtsune/embyToLocalPlayer/releases)
2. 安装油猴脚本。 [发布页](https://greasyfork.org/zh-CN/scripts/448648-embytolocalplayer)
3. 安装 Python (勾选 add to path) [官网](https://www.python.org/downloads/)
4. 修改播放器路径，以及修改播放器选择 `embyToLocalPlayer_config.ini`

> 前置说明

* 网页闪一下是自动关闭兼容流提示。
* 播放器要退出触发回传进度。

> Windows

* 双击 `embyToLocalPlayer_debug.bat`
* 若无报错，按 1（窗口运行），可网页播放测试。（点击原来的播放按钮就可以）
* 按 2 则创建开机启动项并后台运行。
* 问题排查：
    * 若提示找不到 Python，轮流尝试安装以下三种 Python 安装程序：  
      通用流程：卸载 Python > 重启 > 安装 Python (勾选 add to path) > 重启 >  双击 `.bat`
        * 1：[官网](https://www.python.org/downloads/)
        * 2：[Miniconda](https://docs.conda.io/en/latest/miniconda.html)
        * 3：微软商店
    * 若自启失败，检查启动项是否被禁用：任务管理器 > 启动。

> macOS

macOS 可能无法开机自启

1. 刚才保存的文件夹 > 右击 > 新建位于文件夹的终端窗口 `chmod +x *.command` 回车。
2. 双击 `emby_script_run.command`, 若无报错，可播放测试。
3. 开机自启（无窗口运行）：
    1. 启动台 > 自动操作 > 文件 > 新建 > 应用程序 > 运行 Shell 脚本 >   
       把 `emby_script_run.command` 文件拖入 > 点击运行后测试播放 > 文件 > 存储 > 取名并保存到应用程序。
    2. 启动台 > 刚才的应用 > 双击后台运行后再次播放测试。
    3. 系统偏好设置 > 用户与群组 > 登录项 > 添加刚才的应用。
    4. 如果 Monterey 12.6.6 状态栏有齿轮，把文件拖入的操作替换成写以下内容，注意更改cd目录为你保存的目录。  
       `cd ~/App/embyToLocalPlayer && nohup ./emby_script_run.command > run.log 2&>1 &`

> Linux

1. `apt install python3-tk`（没报错不装也行）
2. 添加 `emby_script_run.command` 执行权限，并用终端打开。
3. 正常播放后，加入开机启动项（无窗口运行）：  
   Debian_Xfce：设置 > 会话和启动 > 应用程序自启动

# FAQ

> 通用说明

* Python 最低支持版本为 3.8。
* 用鼠标手势软件关闭播放器体验更舒服一点。
* 同服务器同时开启多个浏览器标签页，会造成回传进度失败假象。手动刷新一下页面，或者只开一个标签。
* Plex 及部分域名有 dns 污染，若无法播放，修改系统 DNS 或使用代理。
* 反馈群组在频道置顶，提问前先把 FAQ 看一遍，不含敏感数据不私聊。  
  小更新会频道提醒，不过应该也没什么更新的了，反馈不需要关注频道。[https://t.me/embyToLocalPlayer](https://t.me/embyToLocalPlayer)

> 如何切换模式

* 点击浏览器油猴插件图标，会有菜单可供点击切换。
* 脚本在当前服务器：启用（默认）；禁用：当前域名不使用脚本。
* 读取硬盘模式：关闭 > 调用本地播放器但使用服务器网络链接。（默认）
* 读取硬盘模式：开启 > 调用本地播放器并转换服务器路径为本地文件地址。前提是本地有文件或挂载。  
  在 `.ini` 里填好路径替换规则，服务端在本地则不用填。`.bat` 按 4 有辅助配置程序
* 持久性缓存模式：只看配置文件，与油猴设置不冲突，不需要开启读取硬盘模式。

> 如何更新

* 将 `_config.ini` 重命名为 `.ini`，其他全删除。再次 GitHub 下载解压当前文件夹。（`.ini` 优先于 `_config.ini`  ）
* 同时看看 `embyToLocalPlayer_config.ini` 有没有新内容。
* 油猴脚本也记得要更新。

> 如何反馈

1. 运行 `debug.bat` 选1。（ macOS 或 Linux 运行 `.command`)  
   若无正常日志输出，命令行输入 `python --version` 检查 python 是否安装成功及版本。  
   Python 低于 3.8.10 的先升级试试看。
2. 换播放器及换视频文件测试是否复现。
3. 截图或复制 `.bat` 窗口中的日志（选中后回车即复制）。
4. 碰到什么问题及怎么复现。

> 字幕相关

* Emby 里字幕选择无效。  
  外挂字幕选择有效，内置字幕会被忽略，由播放器选择。  
  视频文件的内置字幕当作外挂字幕处理会导致播放器语言设置失效。（外挂字幕最优先）  
  正常播放器都可以设置语言优先顺序。

> 播放列表（连续播放|多集回传）相关

* 在配置文件里 `[playlist]` 中启用。（局域网用户已默认启用）
* 播放列表添加完成前最好不退出

* Windows:

    * mpv:
    * mpv.net:
    * vlc:
    * mpc: be: 播放列表条目超过10个可能会卡住，hc 没这问题。
    * pot: 若日志显示`KeyError: 'stream.mkv'`，看下方 FAQ。  
      pot: 下一集无法添加 http 外挂字幕。

* macOS

    * mpv:
    * iina: 仅读盘模式支持并可回传
    * vlc: 下一集无法添加 http 外挂字幕。

* Linux

    * mpv:
    * vlc: 下一集无法添加 http 外挂字幕。

## 播放器相关:

> mpv.net

* 设置播放完自动关闭。不加载下个文件。（触发回传进度）  
  右击 > Settings > Playback > idle:no, auto-load-folder:no （大概是这样

> PotPlayer

* 若碰到问题，本地用户可考虑：[MPC-HC](https://github.com/clsid2/mpc-hc/releases) 自带 LAV，同样支持 madVR MPCVR BFRC 等。  
  网络用户或没有特殊需求的话，mpv 系的播放器综合体验较好。
* 选项 > 播放 > 播放窗口尺寸：全屏
* 配置/语言/其他 > 收尾处理 > 播放完当前后退出（触发回传进度）
* Pot 自身问题：`.bat` 日志可能提示`KeyError: 'stream.mkv'`。  
  解决方案：三选一（若前两个方法失败换版本估计也不行）。1. 本地用户使用读盘模式；2. 把 `.ini` 文件里`多集回传` 部分删除。3. 换
  pot版本；  
  [PotPlayerSetup64-230208.exe](https://www.videohelp.com/download/PotPlayerSetup64-230208.exe)
  可以换这个版本，文件与官网一致。   
  sha1sum `fcd6404e32e6d28769365d9493627f15a0a302d5`
* Pot 自身问题：若使用 http 播放，可能提示地址关闭。Win8 32bit 碰到。  
  解决方案：本地用户使用读盘模式，或者换 pot 便携版。  
  安全性未知：[PotPlayerPortable-220914.zip](https://www.videohelp.com/download/PotPlayerPortable-220914.zip)  
  先打开 `PotPlayerPortable.exe` 一次，但播放用 `C:\<path_to>\PotPlayerPortable\App\PotPlayer\PotPlayer.exe`  
  不然会要求管理员权限运行。
* Pot 自身问题：`.bat` 日志可能提示`请求的操作需要提升`。  
  解决方案：升降级 pot 或者用 32bit 版本。

> MPC：

* 会自动开启 WebUI，系统防火墙提示的时候可以拒绝（不影响使用）。
* 会自动开启 WebUI，建议仅允许从 localhost 访问： 查看 > 选项 > Web 界面：  
  打勾 仅允许从 localhost 访问
* MPC 播放 http 具有加载和拖动慢，视频总时长可能有误的缺点。  
  以及点击关闭播放器后，进程可能残留在后台。

> IINA

* 退出播放器才会回传进度。
* 非读盘模式不支持外挂字幕文件（mpv 支持）

## 其他:

> Trakt 单向同步功能

* 缺点：
    1. 媒体服务器一般本身就有 Trakt 插件。
    2. 只能往 Trakt 单向同步。
    3. 只在播放器正常关闭后，同步播放器已播放的（网页点击已播放不触发）。
    4. 配置和使用都麻烦。
* 使用说明：
    1. 安装依赖：命令行终端运行，安装失败尝试在启用或禁用代理的环境来安装：  
       `python -m pip install requests`  
       或者：  
       `python -m pip install requests -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host=mirrors.aliyun.com`
    2. [点击访问：Trakt app 管理页面](https://trakt.tv/oauth/applications)：   
       创建 app，名字任意，Redirect uri 填写: `http://localhost/trakt` ，然后保存。
    3. ini 配置文件`[trakt]` 填写 `enable_host` `user_name` `client_id` `client_secret` 这四项。
    4. 点击 app 详情页面的 `Authorize` 按钮，二次同意后，复制网址并填到配置文件 `oauth_code` 里。
    5. 启动脚本，播放一个视频，拖到最后，关闭播放器。看日志是否同步成功。
* 常见问题：
    1. 若同步失败。电影看是否缺失IMDb，剧集看单集下方是否有 IMDb 或 TheTVDB。
    2. 目录下`trakt_token.json`可以复制给新电脑用。然后删除原来的，并填写新的 `oauth_code` 来重新生成。   
       如果只是复制到新电脑，重复使用 token 的话，有效期只有三个月。

> bangumi.tv（bgm.tv） 单向同步功能

* 缺点：
    1. 只能往 Bangumi 单向同步。
    2. 只在播放器正常关闭后，同步播放器已播放的（网页点击已播放不触发）。
    3. 只支持常规剧集，不支持剧场版等。
    4. 不支持 Plex。
* 使用说明：
    1. 安装依赖：命令行终端运行，安装失败尝试在启用或禁用代理的环境来安装：  
       `python -m pip install requests`  
       或者：  
       `python -m pip install requests -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host=mirrors.aliyun.com`
    2. 访问并创建令牌 [https://next.bgm.tv/demo/access-token](https://next.bgm.tv/demo/access-token)：   
       复制令牌到 ini 配置文件 `[bangumi]` 部分，` access_token = ` 里
    3. ini 配置文件 `[bangumi]` 填写 `enable_host` `user_name` 这两项。
    4. 启动脚本，播放一集动漫，拖到最后，关闭播放器。看日志是否同步成功。
* 常见问题：
    1. 5季或者50集以上的条目暂不支持。
    2. 日志提示 `Unauthorized` 一般是令牌过期或者没填对，Windows 会自动弹出令牌生成页面。
    
> Jellyfin 相关

* 首页播放结束后，10秒内重复播放**同文件**，本地播放器收到的播放时间会有误。    
  解决方法：
    1. 进详情后再播放没这问题；~~说明不是我的锅~~
    2. 等待10秒后再继续播放；
    3. 手动刷新页面后播放；
    4. ~~告诉我要发送什么请求可以解决这个问题~~

> Plex 相关

* 可能 dns 污染，若无法播放。修改系统 DNS 或使用代理。
* PotPlayer  
  播放 http 时无法读取外挂字幕，读取硬盘模式却可以。（字幕手动上传的，本地硬盘没有，比较玄学）
* 会提示回放错误，随便点一下就会消失。

> 弹弹play 相关

* 若通过 http 播放，有以下缺点：
    1. 每次播放需要选择弹幕。（已把文件名发送给播放器匹配）
    2. 启动时无法及时跳转到 Emby 开始时间，需要播放开始后等待15秒。（每次看完一集则不影响）
    3. 无法加载外挂字幕。

> 持久性缓存（边下边播）相关

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
    3. 未核实：用密匙升级为工作站版，或数字权利工具转换。
    4. 开虚拟机或别的电脑有工作站版，然后直通硬盘并格式化成 ReFS 给 Win10 用（专业版测试可行）。  
       Win8.1 有人改注册表支持。
* 网页点击播放时弹出菜单：
    1. 播放：当缓存进度大于播放开始时间时用缓存播放。其他情况回退网络模式。
    2. 下载 1% 后播放：等待下载首尾各 1% 后启动播放器。其他等同于播放。
    3. 下载（首尾优先）：优先下载首尾各 1% ，可边下边播。
    4. 下载（顺序下载）：不能边下边播。
    5. 删除当前下载
    6. 下载管理器

> 感谢

* [iwalton3/python-mpv-jsonipc](https://github.com/iwalton3/python-mpv-jsonipc)