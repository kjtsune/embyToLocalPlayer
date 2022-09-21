// ==UserScript==
// @name         embyToLocalPlayer
// @name:zh-CN   embyToLocalPlayer
// @name:en      embyToLocalPlayer
// @namespace    https://github.com/kjtsune/embyToLocalPlayer
// @version      1.0.6
// @description  需要python。若用 PotPlayer VLC  mpv MPC 播放，可更新服务器观看进度。支持 Jellyfin。
// @description:zh-CN 需要python。若用 PotPlayer VLC  mpv MPC 播放，可更新服务器观看进度。支持 Jellyfin。
// @description:en  Require python. If you use PotPlayer or VLC or mpv or MPC , will update watch history to emby server. Support Jellyfin.
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

2022-09-21:
1. 增加 PotPlayer 回传进度支持。
2. 增加 VLC 回传进度支持。

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
    if (url.indexOf('/PlaybackInfo?UserId') > -1 && url.indexOf('IsPlayback=true') > -1
        && localStorage.getItem('webPlayerEnable') != 'true') {
        let response = await originFetch(url, request);
        let data = await response.clone().json()
        embyToLocalPlayer(url, request, data);
        console.log('%c%o%s', "color:orange;", 'headers ', response, typeof (response))

        // // 不知道回传什么数据 jellyfin 才不会网页播放，且不转圈。emby 会弹无兼容数据流
        // if (url.indexOf('Emby-Token') != -1) { return '' }
        // data.MediaSources[0].SupportsTranscoding = false;
        // data.MediaSources[0].SupportsDirectPlay = false;
        // data.MediaSources[0].SupportsProbing = false;
        // data.MediaSources[0].Container = 'mkv';
        // console.log('%c%o%s', "color:orange;", 'data ', JSON.stringify(data), typeof (data))
        // var myBlob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        // var init = { "status" : 200 , "statusText" : "SuperSmashingGreat!" };
        // var myResponse = new Response(myBlob, init);
        // return myResponse

    }
    // else if (localStorage.getItem('webPlayerEnable') != 'true' && url.indexOf('/stream') != -1) {
    //     console.log('%c%o%s', "color:orange;", 'url', url)
    //     return
    // }
    else {
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

setModeSwitchMenu('webPlayerEnable', '网页播放模式已经')
setModeSwitchMenu('mountDiskEnable', '读取硬盘模式已经')
