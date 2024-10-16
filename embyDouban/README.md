## embyDouban

emby 里增加：豆瓣 Bangumi bgm.tv 评分 链接

- 豆瓣评论：点击油猴插件后能看到开关。
- 豆瓣链接：评分可点击，或在底部 IMDb 链接前面。
- 番组链接：评分可点击，或在底部 在 TMDB 链接前面。

![](https://github.com/kjtsune/embyToLocalPlayer/raw/main/embyDouban/embyDouban.jpg)

**FAQ**

* 豆瓣：为了合理使用 api，默认只请求一次并缓存。  
  但偶尔可能碰到你的 ip 或者设备被豆瓣拉黑，不返回。现象是豆瓣有这条目并且 imdb id 正确，但没显示。  
  可以换设备和 ip 测试。或者三天后再看看，出错的浏览器缓存脚本会保留三天。
* bgm.tv: 如果匹配不成功，会不显示评分，但显示链接。不过链接一般也是错误的。  
  评分缓存策略：大概是老番30天，新番3天。

**其他相关脚本**

* [embyToLocalPlayer](https://greasyfork.org/zh-CN/scripts/448648-embytolocalplayer)
  ：调用本地播放器。需要 Python。支持回传播放进度。
* [linkDoubanTrakt](https://greasyfork.org/zh-CN/scripts/449899-linkdoubantrakt)
  ：Douban Trakt 增加互相跳转链接。

**感谢**

- [JayXon/MoreMovieRatings](https://github.com/JayXon/MoreMovieRatings)
