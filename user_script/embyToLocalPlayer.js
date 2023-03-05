// ==UserScript==
// @name         embyToLocalPlayer
// @name:zh-CN   embyToLocalPlayer
// @name:en      embyToLocalPlayer
// @namespace    https://github.com/kjtsune/embyToLocalPlayer
// @version      1.1.5.1
// @description  需要 Python。Emby 调用外部本地播放器，并回传播放记录。适配 Jellyfin Plex。
// @description:zh-CN 需要 Python。Emby 调用外部本地播放器，并回传播放记录。适配 Jellyfin Plex。
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
2023-02-16:
1. 分离播放前回传。（提升非本地用户播放器启动速度）
* 版本间累积更新：
  * 适配：网盘直链重定向。
  * 油猴：适配背景视频。
  * 增加：脚本代理及 mpv 系播放器代理。
  * 播放列表：首集进度被重置。
  * 日志：模糊域名及密钥。

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
*/

let fistTime = true;

let config = { logLevel: 2 };

let logger = {
    error: function (...args) {
        if (config.logLevel >= 1)
            console.log('%cerror', 'color: yellow; font-style: italic; background-color: blue;',
                args);
    },
    info: function (...args) {
        if (config.logLevel >= 2)
            console.log('%cinfo', 'color: yellow; font-style: italic; background-color: blue;',
                args);
    },
    debug: function (...args) {
        if (config.logLevel >= 3)
            console.log('%cdebug', 'color: yellow; font-style: italic; background-color: blue;',
                args);
    },
}

async function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function removeErrorWindows() {
    let okButtonList = document.querySelectorAll('button[data-id="ok"]');
    let state = false;
    for (let index = 0; index < okButtonList.length; index++) {
        const element = okButtonList[index];
        if (element.textContent.search(/(了解|好的|知道|Got It)/) != -1) {
            element.click();
            state = true;
        }
    }

    let jellyfinSpinner = document.querySelector('div.docspinner');
    if (jellyfinSpinner) {
        jellyfinSpinner.remove();
        state = true;
    };

    return state;
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
    if (url.indexOf('/PlaybackInfo?UserId') > -1 && url.indexOf('IsPlayback=true') > -1
        && localStorage.getItem('webPlayerEnable') != 'true') {
        let response = await originFetch(url, request);
        let data = await response.clone().json();
        if (data.MediaSources[0].Path.search(/\Wbackdrop/i) != -1) {
            logger.info('backdrop found');
            return originFetch(url, request);
        }
        embyToLocalPlayer(url, request, data);
    } else {
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
    for (const times of Array(15).keys()) {
        await sleep(200);
        if (removeErrorWindows()) {
            logger.info(`remove error window used time: ${(times + 1) * 0.2}`);
            break;
        };
    }
    fistTime = false;
}

function sendDataToLocalServer(data, path) {
    let url = `http://127.0.0.1:58000/${path}/`
    GM_xmlhttpRequest({
        method: 'POST',
        url: url,
        data: JSON.stringify(data),
        headers: {
            'Content-Type': 'application/json'
        },
    });
}

function initXMLHttpRequest() {
    let open = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function (...args) {
        // 正常请求不匹配的网址       
        let url = args[1]
        if (url.indexOf('playQueues?type=video') == -1) {
            return open.apply(this, args);
        }
        // 请求前拦截
        if (url.indexOf('playQueues?type=video') != -1
            && localStorage.getItem('webPlayerEnable') != 'true') {
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
