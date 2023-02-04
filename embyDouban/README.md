## embyDouban

emby 里增加豆瓣 评分 链接 评论(可关)

- 评分：imdb评分前，两者中间五角星
- 链接：底部 imdb 链接前
- 评论：点击油猴插件后能看到开关

**其他相关脚本**

* [embyToLocalPlayer](https://greasyfork.org/zh-CN/scripts/448648-embytolocalplayer)
  ：调用本地播放器。需要 Python。支持回传播放进度。
* [linkDoubanTrakt](https://greasyfork.org/zh-CN/scripts/449899-linkdoubantrakt)
  ：Douban Trakt 增加互相跳转链接。

![](https://github.com/kjtsune/embyToLocalPlayer/raw/main/embyDouban/embyDouban.jpg)

**重置缓存**

* 复制下方代码 > Emby 首页 > F12 > Console > 粘贴 > 回车。  
* 为了合理使用豆瓣，默认只请求一次并缓存。  
  但偶尔可能碰到你的 ip 被豆瓣拉黑，不返回。现象是豆瓣有这条目并且 imdb id 正确，但没显示。  
  这种情况多的话，可以去豆瓣登录（我没登录），隔段时间清空缓存再试试看。
* 不影响使用的话，不建议清空缓存，数据占用很少，而且缓存加载快。

```
function cleanLocalStorage() {
    for (i in localStorage) {
        if (i.search(/^tt/) != -1 || i.search(/\d{8}/) != -1) {
            console.log(i);
            localStorage.removeItem(i);
        }
    }
}
cleanLocalStorage();
```

**感谢**

- [JayXon/MoreMovieRatings](https://github.com/JayXon/MoreMovieRatings)
