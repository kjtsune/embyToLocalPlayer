# embyToLocalPlayer-Python

* Emby/Jellyfin 调用 PotPlayer mpv IINA MPC VLC 播放，并回传播放进度（可关）。适配 Plex。
* 本地需要安装 Python

**特性**

* 在首页也可以播放。点击原来的播放按钮就可以。播放无需二次确认。
* 播放列表（连续播放）支持，下一集保持相同版本。可设置版本偏好。
* trakt.tv bangumi.tv bgm.tv 单向标记已观看支持。
* 本地挂载用户：可跳转到路径对应文件夹。（按钮在网页显示文件路径的上面）
* 可持久性缓存文件到本地。
* 未适配的播放器一般也能用，只是不会回传进度。

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
* IINA（macOS）[发布页](https://iina.io/) 若使用 http 播放不支持外挂字幕文件（mpv 支持）

### 使用说明

> 基础配置

1. 下载 `embyToLocalPlayer.zip` 并解压到任意文件夹。 [发布页](https://github.com/kjtsune/embyToLocalPlayer/releases)
2. 安装油猴脚本。 [发布页](https://greasyfork.org/zh-CN/scripts/448648-embytolocalplayer)
3. 安装 Python (勾选 add to path) [官网](https://www.python.org/downloads/)
4. 修改播放器路径，以及修改播放器选择 `embyToLocalPlayer_config.ini`

> 前置说明

* 网页闪一下是自动关闭兼容流提示。
* 播放器要退出触发回传进度。
* **碰到问题先参考下方相关 FAQ**。

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

1. 刚才保存的文件夹 > 右击 > 新建位于文件夹的终端窗口 `chmod +x *.command` 回车。
2. 双击 `emby_script_run.command`, 若无报错，可播放测试。
3. 开机自启（无窗口运行）：
    1. 方案一：直接进入下一步，但估计只适用于 Monterey 12 及之前的老版本系统。  
       方案二：在终端使用 Homebrew 安装 screen。  
       `brew install screen`  
       如果你没有安装 Homebrew，请先安装 Homebrew。  
       `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install.sh)"`
    2. 启动台 > 自动操作 > 文件 > 新建 > 应用程序 > 运行 Shell 脚本 >   
       把 `emby_script_run.command`（方案一）| `emby_script_run_via_screen.command`（方案二） 文件拖入 >
       点击运行后测试播放 > 文件 > 存储 > 取名并保存到应用程序。
    3. 启动台 > 刚才的应用 > 双击后台运行后再次播放测试。
    4. 系统偏好设置 > 用户与群组 > 登录项 > 添加刚才的应用。
    5. 如果 Monterey 12.6.6 状态栏有齿轮，把文件拖入的操作替换成写以下内容，注意更改cd目录为你保存的目录。  
       `cd ~/App/embyToLocalPlayer && nohup ./emby_script_run.command > run.log 2&>1 &`

> Linux

1. `apt install python3-tk`（没报错不装也行）
2. 添加 `emby_script_run.command` 执行权限，并用终端打开。
3. 正常播放后，加入开机启动项（无窗口运行）：  
   Debian_Xfce：设置 > 会话和启动 > 应用程序自启动。  
   注意：只能使用用图形界面的自启动功能。利用 systemd 自启弹不出播放器，应该是权限或者环境等问题。

### FAQ

**如果排版有问题，请到 GitHub 查看。**  
https://github.com/kjtsune/embyToLocalPlayer#faq

<details>
<summary>通用 FAQ</summary>

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

* 方法1：  
  Windows: `.bat` 按 6  
  Linux / macOS：在 `.ini` 所在的文件夹打开终端，运行 `python3 utils/update.py`  
  查看新旧配置的差异字段。`embyToLocalPlayer_diff.ini`
* 方法2：将 `_config.ini` 重命名为 `.ini`，其他全删除。再次 GitHub 下载解压当前文件夹。（`.ini` 优先于 `_config.ini`  ）  
  同时看看 `embyToLocalPlayer_config.ini` 有没有新内容。
* 油猴脚本有时也要更新。

> 如何反馈

1. 运行 `debug.bat` 选1。（ macOS 或 Linux 运行 `.command`)  
   若无正常日志输出，命令行输入 `python --version` 检查 python 是否安装成功及版本。  
   Python 低于 3.8.10 的先升级试试看。
2. 换播放器及换视频文件测试是否复现。
3. 截图或复制 `.bat` 窗口中的日志（选中后回车即复制）。
4. 碰到什么问题及怎么复现。
5. [可选] 开启日志文件会隐藏报错里的用户名 `.ini` > `[dev]` > `log_file`

> 字幕相关

* Emby 里字幕选择无效。  
  外挂字幕选择有效，内置字幕会被忽略，由播放器选择。  
  视频文件的内置字幕当作外挂字幕处理会导致播放器语言设置失效。（外挂字幕最优先）  
  正常播放器都可以设置语言优先顺序。

> 播放列表（连续播放|多集回传）相关

* 在配置文件里 `[playlist]` 中配置。
* 播放列表添加完成前最好不退出（大部分没事）

* Windows:

    * mpv:
    * mpv.net:
    * vlc:
    * mpc: be: 播放列表条目超过10个可能会卡住，hc 没这问题。
    * pot: 若日志显示`KeyError: 'stream.mkv'`，看下方 FAQ。  
      pot: 采用连播模式解决：播放列表下一集无法添加 http 外挂字幕。

* macOS

    * mpv:
    * iina: 仅读盘模式支持并可回传
    * vlc: 采用连播模式解决：播放列表下一集无法添加 http 外挂字幕。

* Linux

    * mpv:
    * vlc: 采用连播模式解决：播放列表下一集无法添加 http 外挂字幕。

</details>

<details>
<summary>观看记录存储服务相关</summary>

### 观看记录存储服务相关

> 通用 FAQ

* Clash for Windows 用户：
    * 日志报错：`SSLEOFError(8, 'EOF occurred in violation of protocol (_ssl.c:1129)'))`
    * 解决方案：Clash > Settings > System Proxy > Specify Protocol > 启用。

> bangumi.tv（bgm.tv） 单向同步（点格子）

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
    1. 5季或者90集以上的条目暂不支持。
    2. 日志提示 `Unauthorized` 一般是令牌过期或者没填对，Windows 会自动弹出令牌生成页面。
    3. 由于 `bgm.tv` 的 `续集` 不一定是下一季，导致第几季可能关联错误（经下面处理后概率低）。  
       目前把 `续集` 里：集数大于3，同时第一集的序号小于2的 `续集` 当作下一季的开始。  
       且只保留类型为 TV 的续集（`类型在标题右侧灰字`），跳过类型为 OVA 剧场版 WEB 等的。
       如果同步的集序号小于12（不会是分批次放送），还会核查 Emby 里的季上映时间（一般是 TMDb 的时间）与 bgm.tv
       的上映时间相差是否超过15天，来保证准确性。  
       如果还有其他特殊情况，可以反馈。

> trakt.tv 单向同步

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

</details>

<details>
<summary>播放器相关</summary>

### 播放器相关:

> mpv

* 日志正常调用却无法播放：  
  可能是解码方面的问题，换视频或者软解看看，检查 mpv 日志。  
  `mpv.conf` > `log-file = <save path>`

> mpv.net

* 设置播放完自动关闭。不加载下个文件。（方便触发回传进度，`.ini`配置有播放列表选项）  
  右击 > Settings > Playback > idle:no, auto-load-folder:no （大概是这样

> PotPlayer

* 若碰到问题，本地用户可考虑：[MPC-HC](https://github.com/clsid2/mpc-hc/releases) 自带 LAV，同样支持 madVR MPCVR BFRC 等。  
  网络用户或没有特殊需求的话，mpv 系的播放器综合体验较好。
* 选项 > 播放 > 播放窗口尺寸：全屏
* 配置/语言/其他 > 收尾处理 > 播放完当前后退出（触发回传进度）
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
* 非读盘模式不支持外挂字幕文件（mpv 支持）

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

</details>

<details>
<summary>隐藏功能（一般用不到 / 配置麻烦 / 无支持）</summary>

### 隐藏功能（无支持）:

> 播放列表预读取下一集

* 需要配合 nginx 反代管理缓存，比较麻烦。(在本机或者 nas 运行一个 nginx，缓存并切片视频流)
* 浏览器访问局域网的反代站，或配合后续的 模拟 302 重定向视频流。才能起到缓存效果。
* 填写位置：`.ini` > playlist
    ```
    # 播放进度超过 50% 时触发预读取，预读取下一集。
    prefetch_percent = 50
    
    # 服务端路径包含以下前缀才预读取，逗号隔开，全部启用就留空或删除。
    prefetch_path = /disk/od/TV, /disk/gd
    
    # 预读取时采用的策略：null | sequence | first_last
    # null：读取并丢弃 首8% 尾2% 的数据，适合 nginx 配置缓存的。按理 rclone 也可以，但实测效果不佳。
    # 不推荐：sequence：gui[顺序下载]，first_last：gui[优先首尾]，gui（边下边播）详见 FAQ。
    prefetch_type = null
    ```
* 网盘和本地硬盘混合使用的话。[可选] 配置本地文件用读盘模式：`.ini` > dev > force_disk_mode_path
* 用自签证书反代 https 的站，可以仅反代视频流，并配置跳过证书验证。`.ini` > dev > skip_certificate_verify  
  不过部分播放器也会校检证书，这个需要自行解决。

> 模拟 302 重定向视频流。

* 若使用预读取下一集，nginx 可以只反代视频流。浏览器访问源站，重定向视频流交给本机。降低 nginx 配置难度。减少 bug。
* 亦可用于采用播放分离的公益服，视频流线路本地重定向。加速访问。
* 填写位置：`.ini` > dev
  ```
  # 网址之间逗号隔开，成对填写。源站, 反代站。
  stream_redirect = http://src.src.com, http://reverse.proxy.com, https://src.abc.org, https://reverse.efg.xyz
  ```

> 预读取继续观看

* 类似预读取下一集。仅处理最近上映的集，适合追更。
* [可选] 在不关机的机器里配置并运行更合适一点。
* 填写位置：`.ini` > dev
  ```
  # 配置格式：网址，user_id，api_key，一个或者多个服务端路径前缀;
  # 服务端路径包含路径前缀才预读取，全部就写 /
  # 各项之间逗号隔开，最后分号结尾。复数服务器需要配置就分号后面继续写。
  # user_id：设置 > 用户 > [用户名] > 看浏览器网址。api_key：设置 > API 密钥。
  prefetch_conf = http://emby.abc.org:8096, user_id, api_key, /, /od/另一个路径前缀;
  ```
* 网址填反代站。若填源站，需要配置上方的重定向视频流到反代站。才能让 nginx 缓存。

</details>