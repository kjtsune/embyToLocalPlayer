// ==UserScript==
// @name         embyToLocalPlayer
// @name:zh-CN   embyToLocalPlayer
// @name:en      embyToLocalPlayer
// @namespace    https://github.com/kjtsune/embyToLocalPlayer
// @version      2024.08.26
// @description  Emby/Jellyfin 调用外部本地播放器，并回传播放记录。适配 Plex。
// @description:zh-CN Emby/Jellyfin 调用外部本地播放器，并回传播放记录。适配 Plex。
// @description:en  Play in an external player. Update watch history to Emby/Jellyfin server. Support Plex.
// @author       Kjtsune
// @match        *://*/web/index.html*
// @match        *://*/*/web/index.html*
// @match        *://*/web/
// @match        *://*/*/web/
// @match        https://app.plex.tv/*
// @icon         https://www.google.com/s2/favicons?sz=64&domain=emby.media
// @grant        unsafeWindow
// @grant        GM_info
// @grant        GM_xmlhttpRequest
// @grant        GM_registerMenuCommand
// @grant        GM_unregisterMenuCommand
// @run-at       document-start
// @connect      127.0.0.1
// @license MIT
// ==/UserScript==
'use strict';

(function () {
    'use strict';
    // 去除首页 Discover Emby Premiere 广告
    let adEle = document.querySelector('div.verticalSection.verticalSection-cards.section-appinfo.emby-scrollbuttons-scroller');
    if (adEle) adEle.style.display = 'none';
    
    let _crackFullPath = Boolean(localStorage.getItem('crackFullPath'));
    let _disableOpenFolder = Boolean(localStorage.getItem('disableOpenFolder'));
    let fistTime = true;
    let config = {
        logLevel: 2,
        disableOpenFolder: _disableOpenFolder, // _disableOpenFolder 改为 true 则禁用打开文件夹的按钮。
        crackFullPath: _crackFullPath,
    };

    let logger = {
        error: function (...args) {
            if (config.logLevel >= 1) {
                console.log('%cerror', 'color: yellow; font-style: italic; background-color: blue;', ...args);
            }
        },
        info: function (...args) {
            if (config.logLevel >= 2) {
                console.log('%cinfo', 'color: yellow; font-style: italic; background-color: blue;', ...args);
            }
        },
        debug: function (...args) {
            if (config.logLevel >= 3) {
                console.log('%cdebug', 'color: yellow; font-style: italic; background-color: blue;', ...args);
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
        logger.info('switchLocalStorage ', key, ' to ', localStorage.getItem(key));
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
        logger.info(path, data);
    }

    async function removeErrorWindowsMultiTimes() {
        for (const times of Array(15).keys()) {
            await sleep(200);
            if (removeErrorWindows()) {
                logger.info(`remove error window used time: ${(times + 1) * 0.2}`);
                break;
            };
        }
    }

    async function embyToLocalPlayer(playbackUrl, request, playbackData, extraData) {
        let data = {
            ApiClient: ApiClient,
            playbackData: playbackData,
            playbackUrl: playbackUrl,
            request: request,
            mountDiskEnable: localStorage.getItem('mountDiskEnable'),
            extraData: extraData,
            fistTime: fistTime,
        };
        sendDataToLocalServer(data, 'embyToLocalPlayer');
        removeErrorWindowsMultiTimes();
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
        let pathDiv = mediaSources.querySelector('div[class^="sectionTitle sectionTitle-cards"] > div');
        if (!pathDiv || pathDiv.className == 'mediaInfoItems' || pathDiv.id == 'addFileNameElement') return;
        let full_path = pathDiv.textContent;
        if (!full_path.match(/[/:]/)) return;
        if (full_path.match(/\d{1,3}\.?\d{0,2} (MB|GB)/)) return;

        let openButtonHtml = `<a id="openFolderButton" is="emby-linkbutton" class="raised item-tag-button 
        nobackdropfilter emby-button" ><i class="md-icon button-icon button-icon-left">link</i>Open Folder</a>`
        pathDiv.insertAdjacentHTML('beforebegin', openButtonHtml);
        let btn = mediaSources.querySelector('a#openFolderButton');
        btn.addEventListener("click", () => {
            logger.info(full_path);
            sendDataToLocalServer({ full_path: full_path }, 'openFolder');
        });
    }

    async function addFileNameElement(url, request) {
        let mediaSources = null;
        for (const _ of Array(5).keys()) {
            await sleep(500);
            mediaSources = getVisibleElement(document.querySelectorAll('div.mediaSources'));
            if (mediaSources) break;
        }
        if (!mediaSources) return;
        let pathDivs = mediaSources.querySelectorAll('div[class^="sectionTitle sectionTitle-cards"] > div');
        if (!pathDivs) return;
        pathDivs = Array.from(pathDivs);
        let _pathDiv = pathDivs[0];
        if (!/\d{4}\/\d+\/\d+/.test(_pathDiv.textContent)) return;
        if (_pathDiv.id == 'addFileNameElement') return;

        let response = await originFetch(url, request);
        let data = await response.json();
        data = data.MediaSources;

        for (let index = 0; index < pathDivs.length; index++) {
            const pathDiv = pathDivs[index];
            let filePath = data[index].Path;
            let fileName = filePath.split('\\').pop().split('/').pop();
            fileName = (config.crackFullPath) ? filePath : fileName;
            let fileDiv = `<div id="addFileNameElement">${fileName}</div> `
            pathDiv.insertAdjacentHTML('beforebegin', fileDiv);
        }
    }


    let serverName = null;
    let episodesInfoCache = []; // ['type:[Episodes|NextUp|Items]', resp]
    let episodesInfoRe = /\/Episodes\?IsVirtual|\/NextUp\?Series|\/Items\?ParentId=\w+&Filters=IsNotFolder&Recursive=true/; // Items已排除播放列表
    // 点击位置：Episodes 继续观看，如果是即将观看，可能只有一集的信息 | NextUp 新播放或媒体库播放 | Items 季播放。 只有 Episodes 返回所有集的数据。
    let playlistInfoCache = null;

    const originFetch = fetch;
    unsafeWindow.fetch = async (url, request) => {
        const raw_url = url;
        let urlType = typeof url;
        if (urlType != 'string') {
            url = raw_url.url;
        }
        if (serverName === null) {
            serverName = typeof ApiClient === 'undefined' ? null : ApiClient._appName.split(' ')[0].toLowerCase();
        }
        // 适配播放列表及媒体库的全部播放、随机播放。限电影及音乐视频。
        if (url.includes('Items?') && (url.includes('Limit=300') || url.includes('Limit=1000')) || url.includes('SpecialFeatures')) {
            let _resp = await originFetch(raw_url, request);
            if (serverName == 'emby') {
                await ApiClient._userViewsPromise.then(result => {
                    let viewsItems = result.Items;
                    let viewsIds = [];
                    viewsItems.forEach(item => {
                        viewsIds.push(item.Id);
                    });
                    let viewsRegex = viewsIds.join('|');
                    viewsRegex = `ParentId=(${viewsRegex})`
                    if (!RegExp(viewsRegex).test(url)) {  // 点击季播放美化标题所需，并非媒体库随机播放。
                        episodesInfoCache = ['Items', _resp.clone()]
                        logger.info('episodesInfoCache', episodesInfoCache);
                        logger.info('viewsRegex', viewsRegex);
                        return _resp;
                    }
                }).catch(error => {
                    console.error("Error occurred: ", error);
                });
            }

            playlistInfoCache = null;
            let _resd = await _resp.clone().json();
            if (url.includes('SpecialFeatures')) {
                _resd.Items = _resd
            }
            if (!_resd.Items[0]) {
                logger.error('playlist is empty, skip');
                return _resp;
            }
            if (['Movie', 'MusicVideo'].includes(_resd.Items[0].Type) || url.includes('SpecialFeatures')) {
                playlistInfoCache = _resd
                logger.info('playlistInfoCache', playlistInfoCache);
            }
            return _resp
        }
        // 获取各集标题等，仅用于美化标题，放后面避免误拦截首页右键媒体库随机播放数据。
        let _epMatch = url.match(episodesInfoRe);
        if (_epMatch) {
            _epMatch = _epMatch[0].split(['?'])[0].substring(1); // Episodes|NextUp|Items
            let _resp = await originFetch(raw_url, request);
            episodesInfoCache = [_epMatch, _resp.clone()]
            logger.info('episodesInfoCache', episodesInfoCache);
            return _resp
        }
        try {
            if (url.indexOf('/PlaybackInfo?UserId') != -1) {
                if (url.indexOf('IsPlayback=true') != -1 && localStorage.getItem('webPlayerEnable') != 'true') {
                    let match = url.match(/\/Items\/(\w+)\/PlaybackInfo/);
                    let itemId = match ? match[1] : null;
                    let userId = ApiClient._serverInfo.UserId;
                    let [playbackResp, mainEpInfo] = await Promise.all([
                        originFetch(raw_url, request),
                        ApiClient.getItem(userId, itemId),
                    ]);
                    let playbackData = await playbackResp.clone().json();
                    let episodesInfoData = episodesInfoCache[0] ? await episodesInfoCache[1].clone().json() : null;
                    episodesInfoData = (episodesInfoData && episodesInfoData.Items) ? episodesInfoData.Items : null;
                    let playlistData = (playlistInfoCache && playlistInfoCache.Items) ? playlistInfoCache.Items : null;
                    episodesInfoCache = []
                    let extraData = {
                        mainEpInfo: mainEpInfo,
                        episodesInfo: episodesInfoData,
                        playlistInfo: playlistData,
                        gmInfo: GM_info,
                        userAgent: navigator.userAgent,
                    }
                    playlistInfoCache = null;
                    logger.info(extraData);
                    if (playbackData.MediaSources[0].Path.search(/\Wbackdrop/i) == -1) {
                        let _req = request ? request : raw_url;
                        embyToLocalPlayer(url, _req, playbackData, extraData);
                        return
                    }
                } else {
                    addOpenFolderElement();
                    addFileNameElement(url, request);
                }
            } else if (url.indexOf('/Playing/Stopped') != -1 && localStorage.getItem('webPlayerEnable') != 'true') {
                return
            }
        } catch (error) {
            logger.error(error, raw_url, url);
            removeErrorWindowsMultiTimes();
            return
        }
        return originFetch(raw_url, request);
    }

    function initXMLHttpRequest() {
        const open = XMLHttpRequest.prototype.open;
        XMLHttpRequest.prototype.open = function (...args) {
            let url = args[1]
            if (serverName === null && url.indexOf('X-Plex-Product') != -1) { serverName = 'plex' };
            // 正常请求不匹配的网址
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
                        let extraData = {
                            gmInfo: GM_info,
                            userAgent: navigator.userAgent,
                        };
                        let data = {
                            playbackData: res,
                            playbackUrl: url,
                            mountDiskEnable: localStorage.getItem('mountDiskEnable'),
                            extraData: extraData,
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

    setModeSwitchMenu('webPlayerEnable', '脚本在当前服务器 已', '', '启用', '禁用', '启用')
    setModeSwitchMenu('mountDiskEnable', '读取硬盘模式已经 ')
})();
