// ==UserScript==
// @name         embyToLocalPlayer
// @name:zh-CN   embyToLocalPlayer
// @name:en      embyToLocalPlayer
// @namespace    https://github.com/kjtsune/embyToLocalPlayer
// @version      1.1.4
// @description  需要 Python。调用外部本地播放器，并回传播放记录。适配 Jellyfin Plex。
// @description:zh-CN 需要 Python。调用外部本地播放器，并回传播放记录。适配 Jellyfin Plex。
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
2023-02-04:
1. 修复：播放进度被重置。
2. 修复：.iso 圆盘禁用回传避免莫名已观看。
3. 适配：.m3u8 直播源。
* 版本间累积更新：
  * 弹弹play: 读盘模式支持多集回传，配置改动。
  * 播放列表: 修复错误的集数限制逻辑。
  * mpc: 修复回传错误。
  * force_disk_mode: 合并到 [dev] 里。
  * 伪随机播放器管道名或端口，增加容错率。
  * 播放器多开。

2022-11-25:
1. 播放列表可预读取下一集。
* 版本间累积更新：
  * 油猴脚本整合自动关闭错误窗口。不再需要 `embyErrorWindows.js`。
  * 播放列表: 适配 Jellyfin
  * 播放列表: 修复 MPC 外挂字幕。
  * 修复 1.1.2 版本首次启动没杀死多余进程。
*/

let fistTime = true;

async function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function removeErrorWindows() {
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
        fistTime: fistTime,
        playbackData: response,
        playbackUrl: playbackUrl,
        request: request,
        mountDiskEnable: localStorage.getItem('mountDiskEnable'),

    };
    sendDataToLocalServer(data, 'embyToLocalPlayer');
    await sleep(100);
    removeErrorWindows();
    fistTime = false;
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
