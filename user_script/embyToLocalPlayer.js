// ==UserScript==
// @name         embyToLocalPlayer
// @name:zh-CN   embyToLocalPlayer
// @name:en      embyToLocalPlayer
// @namespace    https://github.com/kjtsune/embyToLocalPlayer
// @version      1.1.6
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
2023-04-13:
1. 默认读取系统代理。
2. 默认取消播放器多开限制。
* 版本间累积更新：
  * 播放列表: 适配 Plex。
  * 网页可跳转到对应文件夹。（限 Emby，按钮在文件路径上方。可改油猴脚本禁用，有注释。）
  * “检查媒体文件是否存在” 降级为可选功能，缩短启动时间，可在 [dev] 中启用，适用于多网盘配置优先级。

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

let config = {
    logLevel: 2,
    disableOpenFolder: false, // false 改为 true 则禁用打开文件夹的按钮。
};

let fistTime = true;

let logger = {
    error: function (...args) {
        if (config.logLevel >= 1) {
            console.log('%cerror', 'color: yellow; font-style: italic; background-color: blue;', args);
        }
    },
    info: function (...args) {
        if (config.logLevel >= 2) {
            console.log('%cinfo', 'color: yellow; font-style: italic; background-color: blue;', args);
        }
    },
    debug: function (...args) {
        if (config.logLevel >= 3) {
            console.log('%cdebug', 'color: yellow; font-style: italic; background-color: blue;', args);
        }
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

function sendDataToLocalServer(data, path) {
    let url = `http://127.0.0.1:58000/${path}/`;
    GM_xmlhttpRequest({
        method: 'POST',
        url: url,
        data: JSON.stringify(data),
        headers: {
            'Content-Type': 'application/json'
        },
    });
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

function isHidden(el) {
    return (el.offsetParent === null);
}

function getVisibleElement(elList) {
    if (!elList) return;
    if (NodeList.prototype.isPrototypeOf(elList)) {
        for (let i = 0; i < elList.length; i++) {
            if (!isHidden(elList[i])) {
                return elList[i];
            }
        }
    } else {
        return elList;
    }
}

async function addOpenFolderElement() {
    if (config.disableOpenFolder) return;
    let mediaSources = null;
    for (const _ of Array(5).keys()) {
        await sleep(500);
        mediaSources = getVisibleElement(document.querySelectorAll('div.mediaSources'));
        if (mediaSources) break;
    }
    if (!mediaSources) return;
    let pathDiv = mediaSources.querySelector('div[class="sectionTitle sectionTitle-cards"] > div');
    if (!pathDiv || pathDiv.className == 'mediaInfoItems') return;
    let full_path = pathDiv.textContent;
    if (!full_path.match(/[/:]/)) return;

    let openButtonHtml = `<a id="openFolderButton" is="emby-linkbutton" class="raised item-tag-button 
    nobackdropfilter emby-button" ><i class="md-icon button-icon button-icon-left">link</i>Open Folder</a>`
    pathDiv.insertAdjacentHTML('beforebegin', openButtonHtml);
    let btn = mediaSources.querySelector('a#openFolderButton');
    btn.addEventListener("click", () => {
        logger.info(full_path);
        sendDataToLocalServer({ full_path: full_path }, 'openFolder');
    });
}

const originFetch = fetch;
unsafeWindow.fetch = async (url, request) => {
    if (url.indexOf('/PlaybackInfo?UserId') != -1) {
        if (url.indexOf('IsPlayback=true') != -1 && localStorage.getItem('webPlayerEnable') != 'true') {
            let response = await originFetch(url, request);
            let data = await response.clone().json();
            if (data.MediaSources[0].Path.search(/\Wbackdrop/i) == -1) {
                embyToLocalPlayer(url, request, data);
                return
            }
        } else {
            addOpenFolderElement();
        }
    }
    return originFetch(url, request);
}

function initXMLHttpRequest() {
    const open = XMLHttpRequest.prototype.open;
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
