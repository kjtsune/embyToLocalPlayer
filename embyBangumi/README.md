## embyBangumi

使用 Bangumi 的首季评分来填充 Emby 内的烂番茄评分（影评人评分）

### 原理

利用 Emby 从 TMDB 里刮削出的 `原产地名称` 和 `上映时间` ，通过 `api.bgm.tv` 检索评分。

### 使用说明

**ini 文件配置，先保持 `dry_run = yes` 来测试效果。**  
**没有还原功能，使用前做好备份**

1. 下载 `embyBangumi.zip`
   并解压到任意文件夹。[发布页](https://github.com/kjtsune/embyToLocalPlayer/releases/tag/embyBangumi)
2. 根据注释在`_config.ini` 配置文件填写 `host` `api_key` `user_id`这三项。
3. 在解压文件夹里打开终端。
4. 安装依赖：`python -m pip install -i http://pypi.douban.com/simple/ --trusted-host=pypi.douban.com/simple requests`
5. 运行命令：`python embyBangumi.py`
6. 没问题后 `dry_run = no`，再次运行。
7. 媒体库节目列表 > 右上角：••• > 勾选显示：影评人评分

### 其他

* 评分和上映时间都是以首季为准。
* 电影类的上映时间不同地区区别较大，有的会搜索失败。  
  搜索无结果后会把上映时间范围延长200天，再次搜索。准确率会降低。
* 日志出现 `trust < 0.5` ,是因为搜索出来的结果不正确。会跳过不更改。  
  错误的结果会缓存7天，7天后重新运行会再次尝试搜索。
* 剧集类的上映时间一般没问题，所以不会再延长搜索的时间范围二次搜索。  
  日志出现 `not result` 有可能是 NSFW 条目限制。  
  或者 Emby 里的上映日期和 Bangumi 的相差超过两天。  
  `not result` 的状态也会保持7天，7天后运行才会重试。
* 重试大概率还是一样结果。（目前不考虑申请密钥）
* 正确的结果，会根据发布时间长短缓存。90天内发布缓存3天。1年内的缓存30天。超过1年的缓存120天。
