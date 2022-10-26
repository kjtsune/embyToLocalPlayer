// ==UserScript==
// @name         embyToLocalPlayer
// @name:zh-CN   embyToLocalPlayer
// @name:en      embyToLocalPlayer
// @namespace    https://github.com/kjtsune/embyToLocalPlayer
// @version      1.1.1
// @description  需要 Python。调用外部本地播放器，并回传播放记录。支持：纯本地｜网络｜持久性缓存｜下载。适配 Jellyfin Plex。
// @description:zh-CN 需要 Python。调用外部本地播放器，并回传播放记录。支持：纯本地｜网络｜持久性缓存｜下载。适配 Jellyfin Plex。
// @description:en  Require Python. Play in an external player. Update watch history to emby server. Support Jellyfin Plex.
// @author       Kjtsune
// @match        *://*/web/index.html*
// @icon         https://www.google.com/s2/favicons?sz=64&domain=emby.media
// @grant        unsafeWindow
// @grant        GM_xmlhttpRequest
// @grant        GM_registerMenuCommand
// @grant        GM_unregisterMenuCommand
// @run-at       document-start
// @license MIT
// ==/UserScript==
'use strict';
/*
* **如何更新**：  
  将 `_config.ini` 重命名为 `.ini`，其他全删除。再次 github 下载解压当前文件夹。（`.ini` 优先于 `_config.ini`  ）  
* 以前通过 `ahk` 自启的用户，运行`_debug.bat ` 重新添加启动项并手动删除旧的就可以。

2022-10-26:
1. 可选是否回传播放记录。
2. 修复 1.1.0 版本原版 mpv 意外卡死。

2022-10-24:
1. 增加持久性缓存（边下边播）详见 FAQ。
2. 附带下载功能及下载管理。
3. 改为多线程运行。

2022-10-15:
1. Windows：`_debug.bat` 增加一键后台自启，减少 ahk 依赖。  
2. 不再将内置字幕转为外挂字幕。正常播放器都可以设置字幕语言优先顺序。
3. 修复 emby 4.7.8 播放时时间被重置。

2022-10-06:
1. 增加 macOS 支持。mpv VLC。
2. 增加 IINA 支持。
3. 修复 Linux VLC 播放时间获取。

2022-09-27:
1. 增加 弹弹play 支持。（动漫弹幕播放器）
2. 增加 网络模式 与 读盘模式 混合功能。

2022-09-24:
1. 增加 Plex 支持。
2. _debug.ahk 可创建开机启动项

2022-09-21:
1. 增加 PotPlayer 回传进度支持。
2. 增加 VLC 回传进度支持。
3. 修复首次启动时系统编码判断问题。
4. 修复 `.ini` 被记事本修改后可能编码错误。
*/

function switchLocalStorage(key, defaultValue = 'true', trueValue = 'true', falseValue = 'false') {
    if (key in localStorage) {
        let value = (localStorage.getItem(key) === trueValue) ? falseValue : trueValue;
        localStorage.setItem(key, value);
    } else {
        localStorage.setItem(key, defaultValue)
    }
    console.log('switchLocalStorage ', key, ' to ', localStorage.getItem(key))
}

function setModeSwitchMenu(storageKey, menuStart = '', menuEnd = '', defaultValue = '关闭', trueValue = '开启', falseValue = '关闭') {
    let switchNameMap = { 'true': trueValue, 'false': falseValue, null: defaultValue };
    let menuId = GM_registerMenuCommand(menuStart + switchNameMap[localStorage.getItem(storageKey)] + menuEnd, clickMenu);

    function clickMenu() {
        GM_unregisterMenuCommand(menuId);
        switchLocalStorage(storageKey)
        menuId = GM_registerMenuCommand(menuStart + switchNameMap[localStorage.getItem(storageKey)] + menuEnd, clickMenu);
    }

}

const originFetch = fetch;
unsafeWindow.fetch = async (url, request) => {
    // console.log('%c%o%s', 'background:yellow;', url, ' MYLOG')
    if (url.indexOf('/PlaybackInfo?UserId') > -1 && url.indexOf('IsPlayback=true') > -1
        && localStorage.getItem('webPlayerEnable') != 'true') {
        let response = await originFetch(url, request);
        let data = await response.clone().json()
        embyToLocalPlayer(url, request, data);
    } else {
        // console.log('%c%o%s', "color:orange;", 'url ', url)
        return originFetch(url, request);
    }
}

async function getItemInfo(playbackUrl, request) {
    let response = await fetch(playbackUrl, request);
    if (response.ok) {
        return await response.json();
    } else {
        throw new Error(response.statusText);
    }
}

async function embyToLocalPlayer(playbackUrl, request, response) {
    let data = {
        playbackData: response,
        playbackUrl: playbackUrl,
        request: request,
        mountDiskEnable: localStorage.getItem('mountDiskEnable'),

    };
    sendDataToLocalServer(data, 'embyToLocalPlayer');
}

function sendDataToLocalServer(data, path) {
    let url = `http://127.0.0.1:58000/${path}/`
    GM_xmlhttpRequest({
        method: "POST",
        url: url,
        data: JSON.stringify(data),
        headers: {
            "Content-Type": "application/json"
        },
    });
}

function initXMLHttpRequest() {
    let open = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function (...args) {
        // 正常请求不匹配的网址       
        // console.log(args, "---all_args");
        let url = args[1]
        if (url.indexOf('playQueues?type=video') == -1) {
            return open.apply(this, args);
        }
        // 请求前拦截
        if (url.indexOf('playQueues?type=video') != -1
            && localStorage.getItem('webPlayerEnable') != 'true') {
            // console.log(args, "-----args");
            fetch(url, {
                method: args[0],
                headers: {
                    'Accept': 'application/json',
                }
            })
                .then(response => response.json())
                .then((res) => {
                    let data = {
                        playbackData: res,
                        playbackUrl: url,
                        mountDiskEnable: localStorage.getItem('mountDiskEnable'),

                    };
                    sendDataToLocalServer(data, 'plexToLocalPlayer');
                    // console.log(data, "-----data")
                });
            return;
        }
        return open.apply(this, args);
    }
}

// 初始化请求并拦截 plex
initXMLHttpRequest()

setModeSwitchMenu('webPlayerEnable', '网页播放模式已经 ')
setModeSwitchMenu('mountDiskEnable', '读取硬盘模式已经 ')
