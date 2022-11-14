// ==UserScript==
// @name         embyToLocalPlayer
// @name:zh-CN   embyToLocalPlayer
// @name:en      embyToLocalPlayer
// @namespace    https://github.com/kjtsune/embyToLocalPlayer
// @version      1.1.2
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
2022-11-08:
1. 增加播放列表功能，仅限 Emby，详见 FAQ
2. 增加是否自动全屏
3. VLC 支持外挂字幕
* 版本间累积更新：
    * 修复原版 mpv 切换字幕或音轨卡死。
    * gui 可根据服务器禁用。
    * 若误开读取硬盘模式并播放报错，不用重启脚本。

2022-10-26:
1. 可选是否回传播放记录。
2. 修复 1.1.0 版本原版 mpv 意外卡死。
*/

async function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function removeErrorWindows(){
    let okButtonList = document.querySelectorAll('button[data-id="ok"]');
    for (let index = 0; index < okButtonList.length; index++) {
        const element = okButtonList[index];
        // console.log('%c%o%s', "color:orange;", 'textContent ', element.textContent)
        if (element.textContent.search(/(了解|好的|知道|Got It)/) != -1) {
            element.click();
        }
    }

    let jellyfinSpinner = document.querySelector('div.docspinner');
    if (jellyfinSpinner) { jellyfinSpinner.remove() };

    // let plexPlayerError = document.querySelector('div[class^="PlayerErrorModal-modalHeader"]');
    // let plexErrorWindow = document.querySelector('div[class^="Modal-modalContainer"]');
    // if (plexPlayerError && plexErrorWindow) { location.reload() };
}

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

async function embyToLocalPlayer(playbackUrl, request, response) {
    let data = {
        playbackData: response,
        playbackUrl: playbackUrl,
        request: request,
        mountDiskEnable: localStorage.getItem('mountDiskEnable'),

    };
    sendDataToLocalServer(data, 'embyToLocalPlayer');
    await sleep(100);
    removeErrorWindows();
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
