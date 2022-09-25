// ==UserScript==
// @name         embyToLocalPlayer
// @name:zh-CN   embyToLocalPlayer
// @name:en      embyToLocalPlayer
// @namespace    https://github.com/kjtsune/embyToLocalPlayer
// @version      1.0.7
// @description  需要 Python。若用 PotPlayer VLC mpv MPC 播放，可回传播放进度。支持 Jellyfin Plex。
// @description:zh-CN 需要 Python。若用 PotPlayer VLC mpv MPC 播放，可回传播放进度。支持 Jellyfin Plex。
// @description:en  Require Python. If you use PotPlayer or VLC or mpv or MPC , will update watch history to emby server. Support Jellyfin Plex.
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
更新的同时要去 github 下载文件，方法详见介绍里的 [更新] 部分

2022-09-24:
1. 增加 Plex 支持。
2. _debug.ahk 可创建开机启动项

2022-09-21:
1. 增加 PotPlayer 回传进度支持。
2. 增加 VLC 回传进度支持。
3. 修复首次启动时系统编码判断问题。
4. 修复 `.ini` 被记事本修改后可能编码错误

2022-09-19:
1. 增加 Jellyfin 支持。

2022-09-07:
1. 增加 mpc-hc mpc-be 回传进度支持。
2. 修复 mpv 窗口激活置顶可能失败，无需配置 `ontop = yes`。
3. 修复 mpc 未在前台启动，自动全屏。

2022-09-05：
1. 修复 .vbs .ahk 文件内路径含空格问题。
2. 首次启动会自动关闭之前的进程，方便调试，减少错误。
3. 挂载盘可设优先级（一般用不到）
4. 更新 portable_config 修复一些注释有误的。
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
        if (url.indexOf('playQueues?type=video') == -1 ) {
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
            return ;                
        }
        return open.apply(this, args);
    }
}

// 初始化请求并拦截 plex
initXMLHttpRequest()

setModeSwitchMenu('webPlayerEnable', '网页播放模式已经 ')
setModeSwitchMenu('mountDiskEnable', '读取硬盘模式已经 ')
