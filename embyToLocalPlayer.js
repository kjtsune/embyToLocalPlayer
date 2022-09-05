// ==UserScript==
// @name         embyToLocalPlayer
// @name:zh-CN   embyToLocalPlayer
// @name:en      embyToLocalPlayer
// @namespace    https://github.com/kjtsune/embyToLocalPlayer
// @version      1.0.2
// @description  需要python。若用mpv播放，可更新服务器观看进度。
// @description:zh-CN 需要python。若用mpv播放，可更新服务器观看进度。
// @description:en  Require python. If you use mpv, will update watch history to emby server.
// @author       Kjtsune
// @match        *://*/web/index.html*
// @icon         https://www.google.com/s2/favicons?sz=64&domain=emby.media
// @grant        unsafeWindow
// @grant        GM_registerMenuCommand
// @grant        GM_unregisterMenuCommand
// @run-at       document-start
// @license MIT
// ==/UserScript==
'use strict';
/* 
更新的同时要去 github 下载文件，方法详见介绍里的 [更新] 部分
2022-09-05 ：
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
unsafeWindow.fetch = (...arg) => {
    if (arg[0].indexOf('/PlaybackInfo?UserId') > -1 && arg[0].indexOf('IsPlayback=true') > -1
        && localStorage.getItem('webPlayerEnable') != 'true') {
        embyToLocalPlayer(arg[0]);
        return ''
    }
    else if (arg[0].indexOf('/dialog.template.html') != -1) {
        return
    }
    else {
        return originFetch(...arg);
    }
}

async function getItemInfo(itemInfoUrl) {
    let response = await fetch(itemInfoUrl);
    if (response.ok) {
        return await response.json();
    } else {
        throw new Error(response.statusText);
    }
}


async function embyToLocalPlayer(playbackUrl) {
    let data = {
        playbackData: await getItemInfo(playbackUrl),
        playbackUrl: playbackUrl,
        mountDiskEnable: localStorage.getItem('mountDiskEnable'),

    };
    fetch('http://127.0.0.1:58000/embyToLocalPlayer/', {
        method: 'POST',
        body: JSON.stringify(data)
    })
}

setModeSwitchMenu('webPlayerEnable', '网页播放模式已经')
setModeSwitchMenu('mountDiskEnable', '读取硬盘模式已经')
