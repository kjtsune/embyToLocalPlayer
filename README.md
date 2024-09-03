# etlp - embyToLocalPlayer

etlp - Emby/Jellyfin 调用 PotPlayer mpv IINA MPC VLC 播放，并回传播放进度（可关）。适配 Plex。

**特性**

* 在首页也可以播放。点击原来的播放按钮就可以。可配置版本优先级（若视频多版本）。
* 播放列表（连续播放）支持，下一集保持相同版本。
* trakt.tv bangumi.tv bgm.tv 单向标记已观看支持。
* 本地挂载用户：可跳转到路径对应文件夹。（按钮在网页显示文件路径的上面）
* 未适配的播放器一般也能用，只是不会回传进度。
* 可在 qBittorrent WebUI 里直接播放或者跳转到路径对应挂载文件夹。
  [配套脚本](https://greasyfork.org/zh-CN/scripts/450015-qbittorrent-webui-open-file)

**以下播放器支持回传进度**

* 没特殊要求的话，mpv 系的播放器综合体验较好。
* mpv（纯快捷键）[Windows](https://sourceforge.net/projects/mpv-player-windows/files/64bit/) 。 macOS
  解压后拖到应用程序即可 [macOS](https://laboratory.stolendata.net/~djinn/mpv_osx/)
* mpv.net（可鼠标）[发布页](https://github.com/stax76/mpv.net/releases)。 其他 mpv 内核的播放器一般也可以。
* PotPlayer [发布页](https://potplayer.daum.net/)
  若使用 http 播放，**可能提示地址关闭**， 解决方法在 FAQ。
* MPC-HC [发布页](https://github.com/clsid2/mpc-hc/releases)
* MPC-BE [发布页](https://sourceforge.net/projects/mpcbe/files/MPC-BE/Release%20builds/)
* VLC [发布页](https://www.videolan.org/vlc/)
* IINA（macOS）[发布页](https://iina.io/)

### 使用说明

> 基础配置

1. 下载 `etlp-python-embed-win32.zip` (**便携版** | Windows only)   
   或者 `etlp-mpv-py-embed-win32.zip` (含mpv播放器便携版 | Windows only | 快捷键见 FAQ)  
   或者 `embyToLocalPlayer.zip` (Windows / Linux / macOS)  
   然后解压到任意文件夹。 [发布页](https://github.com/kjtsune/embyToLocalPlayer/releases)
2. 进入文件夹，修改配置文件：`embyToLocalPlayer_config.ini`
   中的播放器路径，以及播放器选择。（若使用含mpv便携版，则无需修改。）  
   \[可选\]：改名为 `embyToLocalPlayer.ini`
3. 安装 Python (勾选 add to path) [官网](https://www.python.org/downloads/)
   （若使用便携版，则无需安装。）
4. 推荐油猴插件，装一个即可
   [Tampermonkey](https://chromewebstore.google.com/detail/lcmhijbkigalmkeommnijlpobloojgfn) |
   [Violentmonkey](https://chrome.google.com/webstore/detail/violent-monkey/jinjaccalgkegednnccohejagnlnfdag) |
   [Tampermonkey v3(不推荐，需启用开发者模式)](https://chromewebstore.google.com/detail/dhdgffkkebhmkfjojejmpbldmpobfkfo)
5. 安装油猴脚本并刷新 Emby 页面。[发布页](https://greasyfork.org/zh-CN/scripts/448648-embytolocalplayer)

> 前置说明

* 网页闪一下是自动关闭兼容流提示。
* 播放器要退出触发回传进度。
* 日志出现 `serving at 127.0.0.1:58000` 为服务启动成功。
* **碰到问题先参考下方相关 FAQ，没按要求反馈会忽略**。

> Windows

1. 双击 `embyToLocalPlayer_debug.bat` （不要右击以管理员身份运行）
2. 若无报错，按 1（不要关闭窗口），然后网页播放测试。（点击原来的播放按钮就可以）
3. 按 2 则创建开机启动项并后台运行。（隐藏窗口运行）

* 问题排查：
    * 若双击 `.bat` 就提示找不到 Python，请使用便携版。
    * 若碰到播放器无法播放，请使用包含 mpv 的便携版测试。
    * 若自启失败，检查启动项是否被禁用：任务管理器 > 启动。  
      `.bat` 按 3 查看开机文件夹里面`embyToLocalPlayer.vbs`是否被杀毒软件删了。  
      若被删，可以自己创建 vbs，然后双击测试是否正常后台运行。 `.vbs` 模板:
      ```
      CreateObject("Wscript.Shell").Run """<Python所在文件夹>\python.exe"" ""<脚本所在文件夹>\embyToLocalPlayer.py""" , 0, True
      ```
    * **反馈前看下方相关 FAQ，没按要求反馈会忽略**

> macOS

1. 刚才保存的文件夹 > 右击 > 新建位于文件夹的终端窗口 `chmod +x *.command` 回车。
2. 双击 `etlp_run.command`, 若无报错，可播放测试。
3. 开机自启（无窗口运行）：
    1. 方案一：直接进入下一步，但估计只适用于 Monterey 12 及之前的老版本系统。  
       方案二：在终端使用 Homebrew 安装 screen。  
       `brew install screen`  
       如果你没有安装 Homebrew，请先安装 Homebrew。  
       `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install.sh)"`
    2. 启动台 > 自动操作 > 文件 > 新建 > 应用程序 > 运行 Shell 脚本 >   
       把 `etlp_run.command`（方案一）| `etlp_run_via_screen.command`（方案二） 文件拖入 >
       点击运行后测试播放 > 文件 > 存储 > 取名并保存到应用程序。
    3. 启动台 > 刚才的应用 > 双击后台运行后再次播放测试。
    4. 系统偏好设置 > 用户与群组 > 登录项 > 添加刚才的应用。
    5. 如果 Monterey 12.6.6 状态栏有齿轮，把文件拖入的操作替换成写以下内容，注意更改cd目录为你保存的目录。  
       `cd ~/App/embyToLocalPlayer && nohup ./etlp_run.command > run.log 2&>1 &`

> Linux

1. `apt install python3-tk`（没报错不装也行）
2. 添加 `etlp_run.command` 执行权限，并用终端打开。
3. 正常播放后，加入开机启动项（无窗口运行）：  
   Debian_Xfce：设置 > 会话和启动 > 应用程序自启动。  
   注意：只能使用用图形界面的自启动功能。利用 systemd 自启弹不出播放器，应该是权限或者环境等问题。

### FAQ

**FAQ 建议到 GitHub 查看。**  
https://github.com/kjtsune/embyToLocalPlayer#faq

<details>
<summary>通用 FAQ</summary>

> 通用说明

* Python 最低支持版本为 3.8。Windows 最低支持版本为 8.1。
* 有时浏览器与 Emby 之间的 ws 链接会断开，造成回传进度失败假象。等待看看或手动刷新一下页面。
* 部分域名及 Plex 域名有 dns 污染，若无法播放，修改系统 DNS 或使用代理。
* 反馈群组在频道置顶，提问前先把 FAQ 看一遍，并**按要求反馈**。不含敏感数据不私聊。  
  小更新会频道提醒，不过应该也没什么更新的了，反馈不需要关注频道。[https://t.me/embyToLocalPlayer](https://t.me/embyToLocalPlayer)

> 如何切换模式

* 在 Emby 页面点击浏览器油猴插件图标，会有菜单可供点击切换。
* 脚本在当前服务器：启用（默认）；禁用：当前域名不使用脚本。
* 读取硬盘模式：关闭 > 调用本地播放器但使用服务器网络链接。（默认）
* 读取硬盘模式：开启 > 调用本地播放器并转换服务器路径为本地文件地址。前提是本地有文件或挂载。  
  在 `.ini` 里填好路径替换规则，服务端在本地则不用填。`.bat` 按 4 有辅助配置程序。  
  出错可尝试设置：`dev` > `path_check = yes` 会检查文件是否存在。兼容性更高，日志更清楚。（但会慢一点）
* 持久性缓存模式：只看配置文件，与油猴设置不冲突，不需要开启读取硬盘模式。

> 如何更新

1. Windows: `.bat` 按 6  
   Linux / macOS：在 `.ini` 所在的文件夹打开终端，运行 `python3 utils/update.py`
2. 查看新旧配置的差异字段。`embyToLocalPlayer_diff.ini`

* 油猴脚本有时也要更新。

> 如何反馈

* **没按要求反馈会忽略。**

1. 运行 `debug.bat` 选1。（ macOS 或 Linux 运行 `.command`)
    * 若启动不成功，Windows 用户换含 mpv 的便携版测试。
    * 参考`如何更新`，更新到最新版后测试。
2. 换播放器及换视频文件测试是否复现。（Windows 用户换含 mpv 的便携版测试）
3. 截图或复制 `.bat` 窗口中的日志（选中后回车即复制），或者提供 `log.txt`。
4. 碰到什么问题及怎么复现。
5. [可选] 关闭模糊日志。 `.ini` > `[dev]` > `mix_log = no`
6. 若调用失败（仍在浏览器里播放，或点击播放后 `.bat` 没有新增日志），反馈时提供在 Emby 页面点击浏览器油猴插件图标后的截图。

> 字幕相关

* Emby 里字幕选择无效。  
  外挂字幕选择有效，内置字幕会被忽略，由播放器选择。  
  视频文件的内置字幕当作外挂字幕处理会导致播放器语言设置失效。（外挂字幕最优先）  
  正常播放器都可以设置语言优先顺序。

> 剧集播放列表（连续播放|多集回传）相关

* 默认已启用，可在配置文件里 `[playlist]` 中修改。
* 播放列表添加完成前最好不退出（大部分没事）
* 特别说明：若是 Emby/Jellyfin 网页上的 全部播放/随机播放/播放列表 ，仅支持电影和音乐视频类型。

* Windows:

    * mpv:
    * mpv.net:
    * vlc:
    * mpc: be: 播放列表条目超过10个可能会卡住，hc 没这问题。
    * pot: 若日志显示`KeyError: 'stream.mkv'`，看下方 FAQ。  
      pot: 下一集无法添加 http 外挂字幕时，会禁用播放列表。  
      pot: 读盘模式可能和美化标题和混合S0的功能冲突，不过不影响使用。

* macOS

    * mpv:
    * iina: 仅读盘模式支持并可回传
    * vlc: 下一集无法添加 http 外挂字幕时，会禁用播放列表。

* Linux

    * mpv:
    * vlc: 下一集无法添加 http 外挂字幕时，会禁用播放列表。

</details>

<details>
<summary>观看记录存储服务相关</summary>

### 观看记录存储服务相关

> 通用 FAQ

* Clash for Windows 用户：
    * 日志报错：`SSLEOFError(8, 'EOF occurred in violation of protocol (_ssl.c:1129)'))`
    * 解决方案：Clash > Settings > System Proxy > Specify Protocol > 启用。

* 使用含 Python 的便携版用户无需安装依赖。其他用户需要安装：命令行终端运行，安装失败尝试在启用或禁用代理的环境来安装：  
  `python -m pip install requests`  
  或者：  
  `python -m pip install requests -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host=mirrors.aliyun.com`

> bangumi.tv（bgm.tv） 单向同步（点格子）

* 缺点：
    1. 只能往 Bangumi 单向同步。
    2. 只在播放器正常关闭后，同步播放器已播放的（网页点击已播放不触发）。
    3. 只支持常规剧集，不支持剧场版等。
* 使用说明：
    1. 访问并创建令牌 [https://next.bgm.tv/demo/access-token](https://next.bgm.tv/demo/access-token)：   
       复制令牌到 ini 配置文件 `[bangumi]` 部分，` access_token = ` 里
    2. ini 配置文件 `[bangumi]` 填写 `enable_host` `user_name` 这两项。
    3. 启动脚本，播放一集动漫，拖到最后，关闭播放器。看日志是否同步成功。
* 常见问题：
    1. 5季或者90集以上的条目暂不支持。
    2. 日志提示 `Unauthorized` 一般是令牌过期或者没填对，Windows 会自动弹出令牌生成页面。
    3. 由于 `bgm.tv` 的 `续集` 不一定是下一季，导致第几季可能关联错误（经下面处理后概率低）。  
       目前把 `续集` 里：集数大于3，同时第一集的序号小于2的 `续集` 当作下一季的开始。  
       且只保留类型为 TV 的续集（`类型在标题右侧灰字`），跳过类型为 OVA 剧场版 WEB 等的。
       如果同步的集序号小于12（不会是分批次放送），还会核查 Emby 里的季上映时间（一般是 TMDb 的时间）与 bgm.tv
       的上映时间相差是否超过15天，来保证准确性。  
       Plex 是核查集上映时间与 bgm.tv 的季上映时间相差是否超过180天，来保证准确性。  
       如果还有其他特殊情况，可以反馈。

> trakt.tv 单向同步

* 缺点：
    1. 媒体服务器一般本身就有 Trakt 插件。
    2. 只能往 Trakt 单向同步。
    3. 只在播放器正常关闭后，同步播放器已播放的（网页点击已播放不触发）。
    4. 配置和使用都麻烦。
* 使用说明：
    1. [点击访问：Trakt app 管理页面](https://trakt.tv/oauth/applications)：   
       创建 app，名字任意，Redirect uri 填写: `http://localhost/trakt` ，然后保存。
    2. ini 配置文件`[trakt]` 填写 `enable_host` `user_name` `client_id` `client_secret` 这四项。
    3. 点击 app 详情页面的 `Authorize` 按钮，二次同意后，复制网址并填到配置文件 `oauth_code` 里。
    4. 启动脚本，播放一个视频，拖到最后，关闭播放器。看日志是否同步成功。
* 常见问题：
    1. 若同步失败。电影看是否缺失IMDb，剧集看单集下方是否有 IMDb 或 TheTVDB。
    2. 目录下`trakt_token.json`可以复制给新电脑用。然后删除原来的，并填写新的 `oauth_code` 来重新生成。   
       如果只是复制到新电脑，重复使用 token 的话，有效期只有三个月。

</details>

<details>
<summary>播放器相关</summary>

### 播放器相关:

> mpv

* 若碰到问题，换官方最新原版及使用默认配置测试。  
  可以换视频或者软解看看，并检查 mpv 日志。  
  `mpv.conf` > `log-file = <save path>`

> mpv_embed

* mpv_embed 主要目的是方便排错与反馈，`mpv.conf` 是我个人的简易配置。
* 相较原版 mpv，只修改了少部分快捷键和配置。  
  并添加增强字幕选择规则脚本（`sub-select.lua` `sub-select.json`）  
  `sub-select.json` 貌似未正确配置，等待你提供正确配置  
  和加载同目录文件脚本 `autoload.lua`

> mpv_embed 快捷键

<details>
<summary>mpv_embed 快捷键</summary>

* 中文文档 [https://hooke007.github.io/official_man/mpv.html#id4](https://hooke007.github.io/official_man/mpv.html#id4)
* 英文文档 [https://mpv.io/manual/master/#keyboard-control](https://mpv.io/manual/master/#keyboard-control)
* 文件位置：`mpv_embed` > `portable_config` > `input.conf`

    ```
    ## 中文文档 https://hooke007.github.io/official_man/mpv.html#id4
    ## 中文文档 https://hooke007.github.io/official_man/mpv.html#input-conf
    ## 英文文档 https://mpv.io/manual/master/#keyboard-control
    ## 默认按键 https://github.com/mpv-player/mpv/blob/master/etc/input.conf
    
    ## 鼠标中键可以点击界面 OSD 按钮，会显示播放列表，字幕列表，音轨列表等的。
    
    
    MBTN_LEFT            ignore                       # <无操作> [左键-单击]
    MBTN_LEFT_DBL        cycle fullscreen             # 切换 全屏状态 [左键-双击]
    MBTN_RIGHT           cycle pause                  # 切换 暂停状态 [右键-单击]
    MBTN_RIGHT_DBL       quit                         # 关闭MPV程序 [右键-双击]
    WHEEL_UP             add volume  10               # 音量 + 10 [滚轮-向上]
    WHEEL_DOWN           add volume -10               # 音量 - 10 [滚轮-向下]
    
    MBTN_MID             cycle fullscreen             # 切换 全屏状态 [中键（按压滚轮）]
    f                    cycle fullscreen             # 切换 全屏状态
    ENTER                cycle fullscreen             # 切换 全屏状态 [回车键]
    
    LEFT                 seek -5                      # 后退05秒 [方向左键]
    RIGHT                seek  5                      # 前进05秒 [方向右键]
    UP                   seek  40                     # 后退40秒 [方向上键]
    DOWN                 seek -40                     # 前进40秒 [方向下键]
    .                    frame-step                   # 下一帧
    ,                    frame-back-step              # 上一帧
    
    [                    add speed -0.1               # 播放速度 -（最小0.01）
    ]                    add speed  0.1               # 播放速度 +（最大100）
    {                    multiply speed 0.5           # 播放速度 半减
    }                    multiply speed 2.0           # 播放速度 倍增
    
    ;                    add chapter -1               # 章节 - (Page Down 也可以)
    '                    add chapter  1               # 章节 + (Page Up 也可以)
    q                    quit-watch-later             # 关闭MPV程序 稍后观看（保存当前文件状态）
    Q                    quit                         # 关闭MPV程序
    
    z                    add sub-delay -0.1           # 字幕同步 预载100ms
    Z                    add sub-delay -1             # 字幕同步 预载1000ms
    x                    add sub-delay +0.1           # 字幕同步 延迟100ms
    X                    add sub-delay +1             # 字幕同步 延迟1000ms
    
    i                    script-binding stats/display-stats           # 临时显示统计信息（此时12340翻页，2/4/0页可方向上下键滚动查看）
    I                    script-binding stats/display-stats-toggle    # 开/关 常驻显示统计信息
    TAB                  script-binding stats/display-stats-toggle    # 开/关 常驻显示统计信息
    `                    script-binding console/enable                # 进入控制台（此时Esc退出）
    DEL                  script-binding osc/visibility                # 切换 内置OSC的可见性
    r                    cycle_values video-rotate 90 180 270 0       # 旋转屏幕方向
     ```

</details>


> mpv.net

* 设置播放完自动关闭。不加载下个文件。（方便触发回传进度，`.ini`配置有播放列表选项）  
  右击 > Settings > Playback > idle:no, auto-load-folder:no （大概是这样

> PotPlayer

* 若碰到问题，本地用户可考虑：[MPC-HC](https://github.com/clsid2/mpc-hc/releases) 自带 LAV，同样支持 madVR MPCVR BFRC 等。  
  网络用户或没有特殊需求的话，mpv 系的播放器综合体验较好。
* 碰到问题时，先尝试初始化 PotPlayer 设置后测试。
* 选项 > 播放 > 播放窗口尺寸：全屏
* 配置/语言/其他 > 收尾处理 > 播放完当前后退出（触发回传进度）
* 读盘模式可能和美化标题和混合S0的功能冲突，不过不影响使用。（FAQ > 隐藏功能 有解决方案）
* `.bat` 日志提示`KeyError: ''`。  
  初始化 pot 和 `.ini` 删除播放列表部分试试看。
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

* 完全退出播放器才会回传进度。
* 非读盘模式不支持播放列表。

</details>

<details>
<summary>其他</summary>

### 其他:

> Jellyfin 相关

* 首页播放结束后，10秒内重复播放**同文件**，本地播放器收到的播放时间会有误。    
  解决方法：
    1. 进详情后再播放没这问题；~~说明不是我的锅~~
    2. 等待10秒后再继续播放；
    3. 手动刷新页面后播放；
    4. ~~告诉我要发送什么请求可以解决这个问题~~

> Plex 相关

* 可能 dns 污染，若无法播放。修改系统 DNS 或使用代理。
* 会提示回放错误，随便点一下就会消失。

> 感谢

* [iwalton3/python-mpv-jsonipc](https://github.com/iwalton3/python-mpv-jsonipc)

</details>

<details>
<summary>隐藏功能（一般用不到 / 配置麻烦 / 无支持）</summary>

### 隐藏功能（无支持）:

<details>
<summary>mpv 自动跳过片头片尾</summary>

* 播放时检查视频章节时长与标题，符合条件时跳过该章节，无二次确认。
* 前提：
    * Emby 成功扫描片头。（测试：禁用脚本，用网页播放时有跳过片头按钮）。视频文件本身无章节时，脚本会自动给 mpv 加片头章节。
    * 或者视频文件自带片头片尾章节。（若章节的标题标准会更准确，例如 "Opening"）
* 填写位置：`.ini` > `[dev]`
  ```
  # 片头有90秒，片尾有91秒，允许5秒钟的误差，片头在前30%里，片尾在70%以后，片头片尾可能的章节名称（逗号隔开，辅助判断，不分大小写）
  # 若要禁用就删除掉，或者在前面加 # 号注释掉。mpv 章节跳转快捷键是 ; ' Page Up Page Down
  # 若含有特殊值 hint_only（可删除），为启用仅提示模式，不自动跳过。需要跳过就按章节跳转快捷键。
  skip_intro = 90, 91, 5, 30, 70, opening, ending, op, ed, hint_only
  ```

</details>

<details>
<summary>mpv bangumi trakt 独立同步脚本</summary>

> mpv bangumi trakt 独立同步脚本

* 使用情景：使用其他工具或客户端调用 mpv 播放 Emby/Jellyfin 视频，需要标记 bangumi trakt 中对应条目为已观看。
* 条件：mpv 播放器，播放网络视频流，播放进度超过 90% 时同步。
* 使用方法：
    1. 下载 `etlp-python-embed-win32.zip` 并解压到任意文件夹。  
       （之前就在用本脚本的，更换为便携版，不要运行两份。或者参考 `FAQ > 观看记录存储服务相关` 自行安装 Python 和依赖。）
    2. 将 lua： `刚才解压的文件夹\utils\others\etlp_sync_bgm_trakt.lua` 移动至 mpv 的脚本文件夹。  
       例如：`mpv.exe 所在目录 > portable_config > scripts > etlp_sync_bgm_trakt.lua`
    3. 修改 `etlp_sync_bgm_trakt.lua` 内 etlp 的保存目录（刚才解压的文件夹路径）
    4. 参考上方 `FAQ > 观看记录存储服务相关` 修改配置文件：`embyToLocalPlayer_config.ini`
    5. 播放一个视频，进度拖到 90% 以上，查看 etlp 日志：`刚才解压的文件夹 > log.txt`。或者查看 mpv 日志。
* 排错方法：使用本项目浏览器调用播放测试。

</details>

<details>
<summary>播放列表预读取下一集</summary>

> 播放列表预读取下一集

* 需要配合 nginx 反代管理缓存，比较麻烦。(在本机或者 nas 运行一个 nginx，缓存并切片视频流)  
  读取并丢弃 首8% 尾2% 的数据。按理 rclone 配置缓存也可以，但实测效果不佳。
* 浏览器访问局域网的反代站，或配合后续的 模拟 302 重定向视频流。才能起到缓存效果。
* 填写位置：`.ini` > `[playlist]`
    ```
    # 播放进度超过 50% 时触发预读取，预读取下一集。
    prefetch_percent = 50
    
    # 服务端路径包含以下前缀才预读取，逗号隔开，全部启用就留空或删除。
    prefetch_path = /disk/od/TV, /disk/gd

    # 启用本功能的域名的关键词，逗号隔开。全部启用就留空或删除。
    prefetch_host = 
    ```
* 网盘和本地硬盘混合使用的话。[可选] 配置本地文件用读盘模式：`.ini` > dev > force_disk_mode_path
* 用自签证书反代 https 的站，可以仅反代视频流，并配置跳过证书验证。`.ini` > dev > skip_certificate_verify  
  不过部分播放器也会校检证书，这个需要自行解决。

</details>

<details>
<summary>模拟 302 重定向视频流</summary>

> 模拟 302 重定向视频流

* 若使用预读取下一集，nginx 可以只反代视频流。浏览器访问源站，重定向视频流交给本机。降低 nginx 配置难度。减少 bug。
* 亦可用于其他重定向视频流服务器。采用本地重定向。加速访问。
* 填写位置：`.ini` > `[dev]`
  ```
  # 网址之间逗号隔开，成对填写。源站, 反代站。
  stream_redirect = http://src.src.com, http://reverse.proxy.com, https://src.abc.org, https://reverse.efg.xyz
  ```

</details>

<details>
<summary>预读取继续观看</summary>

> 预读取继续观看

* 类似预读取下一集。仅处理最近上映的集（7天内），适合追更。
* [可选] 在不关机的机器里配置并运行更合适一点。
* 填写位置：`.ini` > `[dev]`
  ```
  # 配置格式：网址，user_id，api_key，一个或者多个服务端路径前缀;
  # 服务端路径包含路径前缀才预读取，全部就写 /
  # 各项之间逗号隔开，最后分号结尾。复数服务器需要配置就分号后面继续写。
  # user_id：设置 > 用户 > [用户名] > 看浏览器网址。api_key：设置 > API 密钥。
  prefetch_conf = http://emby.abc.org:8096, user_id, api_key, /, /od/另一个路径前缀;
  ```
* 若需要 nginx 缓存：网址填反代站。如果填源站，需要配置上方的重定向视频流到反代站。  
  注意播放链接与预读取链接不一致。 `proxy_cache_key "$arg_MediaSourceId$slice_range";`

</details>

<details>
<summary>追更 TG 通知</summary>

> 追更 TG 通知

* 继续观看更新时，通过 Telegram 机器人发送通知。（每10分钟检测一次）
* 前置依赖：启用 预读取继续观看。
* 填写位置：`.ini` 顶部或底部（单独的配置区域即可，不要填到别的配置里）
    ```
    ##################################################################
    ### v v # # # # # # # # 追更 TG 通知 # # # # # # # # # # # v v ###
    
    [tg_notify]
  
    # 找 @BotFather 创建一个机器人。复制并填写 token。
    bot_token = 
  
    # 点击你创建的机器人，然后点击开始或随便发送信息给你的机器人，最后启动本脚本。机器人会告诉你 chat_id。
    chat_id = 
  
    # chat_id 填写后，重启脚本，会自动测试，提示测试成功的话，本项可以关闭。 
    get_chat_id = yes
  
    # 如果不需要预读取服务，仅通知。就启用本项。
    disable_prefetch = no
  
    # 静音通知时间段，范围间逗号隔开。例如：0-9 0点后9点前。类似针式时钟的时间范围。
    silence_time = 0-9, 12-14
  
    # [可选] 可指定 api, 自行搜索 "TG Bot API 反代", 解决网络连接问题。
    base_url = https://api.telegram.org
    ```

</details>

<details>
<summary>持久性缓存</summary>

> 配置方法

* 填写位置：`.ini` 顶部或底部（单独的配置区域即可，不要填到别的配置里）

    ```
    ##################################################################
    ### v v # # # # # # # 文件缓存（边下边播） # # # # # # # # # # v v ###
    
    [gui]
    
    # 若同时使用播放列表，出现问题属于正常现象，换 mpv 等试试看。
    # 是否需要缓存文件到本地硬盘，播放时会弹菜单。油猴不用开读取硬盘模式。
    enable = no
    
    # 缓存路径：NTFS 支持不很理想，解决方法详见 FAQ
    cache_path = D:\cache
    
    # [可选] 在服务端文件路径包含指定关键词时才弹菜单，否则直接播放。关键词间逗号隔开。
    enable_path = 
    
    # 当播放进度超过 98% ，此时若关闭播放器，则删除缓存。禁用填 100
    delete_at = 98
    
    # 缓存超过 100GB 时删除旧缓存。
    cache_size_limit = 100
    
    # 重启后是否自动开始下载未完成任务
    auto_resume = no
    
    # 下载时的代理，用不到就留空。 http://127.0.0.1:7890
    http_proxy =
    
    # 需要禁用 gui 的域名：所包含的字符串列表，逗号隔开，将根据油猴设置直接播放。
    except_host = localhost, 127.0.0.1, 192.168. , 192-168-, example.com:8096
    ```

> 持久性缓存（边下边播）FAQ

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

</details>

<details>
<summary>弹弹播放器</summary>

> 配置方法

* 填写位置：`.ini` 顶部或底部（单独的配置区域即可，不要填到别的配置里）
    ```
    ##################################################################
    ### v v # # # # # # # # # 弹弹播放器 # # # # # # # # # # # # v v ###
    
    [dandan]
    # 弹弹play 动漫弹幕播放器支持。
    # 播放器需开启远程访问和自动加入媒体库。以及 设置 > 文件关联 > 修复弹弹play专用链。
    
    # 总开关： no 禁用，yes 启用。
    enable = no
    
    # 播放器路径
    exe = C:\Green\dandanplay-x64\dandanplay.exe
    
    # 远程访问端口。远程访问里 ip 改为 127.0.0.1 会比较安全。
    port = 80
    
    # 若远程访问曾经启用过 Web验证，请在这里填写 api密钥，没设置则留空。（注意不是密码）
    api_key =
    
    # 仅当服务端路径包含以下路径时使用弹弹播放，逗号隔开。全部文件都用弹弹播放就留空或删除。
    enable_path = /disk/od/TV, /disk/e/anime, 路径的部分字符也可以, anime
    
    # 通过 http 播放时，是否控制开始时间。需等待播放15秒。
    http_seek = yes
    ```

> 弹弹play FAQ

* 弹弹 api 服务需要10秒左右启动，播放时间太短可能会回传失败。
* 播放器需开启远程访问和自动加入媒体库。以及 设置 > 文件关联 > 修复弹弹play专用链。
* 若通过 http 播放，有以下缺点：
    1. 每次播放需要选择弹幕。（已把文件名发送给播放器匹配）
    2. 启动时无法及时跳转到 Emby 开始时间，需要播放开始后等待15秒。（每次看完一集则不影响）
    3. 无法加载外挂字幕。
* 读盘模式：解决切换设备播放时，进度不一致（读盘模式进度由弹弹存储），同步策略：  
  当 Emby 上的进度大于120秒，但弹弹播放器进度小于30秒时（且 api 启动后未曾超过120秒），
  会调整弹弹播放器进度，使其与 Emby 上的一致，需等待 api 启动。

</details>

<details>
<summary>Pot 读盘模式时：播放列表以 Emby 为准 / 美化播放列表标题</summary>

* 修复情景：
    1. Pot 读盘模式：播放动漫第一季，会漏播 Emby 穿插的 S0 集数。
    2. Pot 读盘模式：Emby 上创建的播放列表无法传递给 Pot。
    3. Pot 读盘模式：剧集播放列表标题错位/缺少。
* 前提条件二选一：
    1. Pot 选项 > 配置 > 用当前方案创建 > 改配置文件名称为 `emby`（用脚本播放时会自动切换为该配置）:  
       Pot 选项 > 左上角切换配置为 emby > 基本 > 相似文件打开策略 > 仅打开选定的文件 > 确定 > 关闭。（仅 emby 播放时由脚本添加播列表）
    2. Pot 选项 > 基本 > 相似文件打开策略 > 仅打开选定的文件。（缺点：用文件管理器播放无播放列表）
* 填写位置：`.ini` > `[dev]`
  ```
  # 启动 Pot 的时候指定配置文件的名称，不需要就清空。
  # 若指定的配置名称不存在，Pot 会回退使用重置后的初始配置。
  pot_conf = emby
  ```
* 填写位置：`.ini` > `[playlist]`
  ```
  # 解决 Pot 读盘模式漏播第零季选集及播放列表标题错位/缺少，播放列表加载会变慢，每秒1集。
  mix_s0 = yes
  ```
* 播放的第一个文件是 S0 的话，会连续播 S0。（通用 Bug，换 mpv 也会这样）

</details>

</details>