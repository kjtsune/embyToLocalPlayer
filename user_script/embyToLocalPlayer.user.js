// ==UserScript==
// @name         embyToLocalPlayer
// @name:zh-CN   embyToLocalPlayer
// @name:en      embyToLocalPlayer
// @namespace    https://github.com/kjtsune/embyToLocalPlayer
// @version      2025.05.03
// @description  Emby/Jellyfin 调用外部本地播放器，并回传播放记录。适配 Plex。
// @description:zh-CN Emby/Jellyfin 调用外部本地播放器，并回传播放记录。适配 Plex。
// @description:en  Play in an external player. Update watch history to Emby/Jellyfin server. Support Plex.
// @author       Kjtsune
// @match        *://*/web/index.html*
// @match        *://*/*/web/index.html*
// @match        *://*/web/
// @match        *://*/*/web/
// @match        https://app.emby.media/*
// @match        https://app.plex.tv/*
// @icon         https://www.google.com/s2/favicons?sz=64&domain=emby.media
// @grant        unsafeWindow
// @grant        GM_info
// @grant        GM_xmlhttpRequest
// @grant        GM_registerMenuCommand
// @grant        GM_unregisterMenuCommand
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_deleteValue
// @run-at       document-start
// @connect      127.0.0.1
// @license MIT
// ==/UserScript==
'use strict';
/*global ApiClient*/

(function () {
    'use strict';
    let fistTime = true;
    let config = {
        logLevel: 2,
        disableOpenFolder: undefined, // undefined 改为 true 则禁用打开文件夹的按钮。
        crackFullPath: undefined,
    };

    const originFetch = fetch;

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

    function myBool(value) {
        if (Array.isArray(value) && value.length === 0) return false;
        if (value !== null && typeof value === 'object' && Object.keys(value).length === 0) return false;
        return Boolean(value);
    }

    async function sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    function isHidden(el) {
        return (el.offsetParent === null);
    }

    function getVisibleElement(elList) {
        if (!elList) return;
        if (Object.prototype.isPrototypeOf.call(NodeList.prototype, elList)) {
            for (let i = 0; i < elList.length; i++) {
                if (!isHidden(elList[i])) {
                    return elList[i];
                }
            }
        } else {
            return elList;
        }
    }

    function _init_config_main() {
        function _init_config_by_key(confKey) {
            let confLocal = localStorage.getItem(confKey);
            if (confLocal == null) return;
            if (confLocal == 'true') {
                GM_setValue(confKey, true);

            } else if (confLocal == 'false') {
                GM_setValue(confKey, false);
            }
            let confGM = GM_getValue(confKey, null);
            if (confGM !== null) { config[confKey] = confGM };
        }
        _init_config_by_key('crackFullPath');
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

    function removeErrorWindows() {
        let okButtonList = document.querySelectorAll('button[data-id="ok"]');
        let state = false;
        for (let index = 0; index < okButtonList.length; index++) {
            const element = okButtonList[index];
            if (element.textContent.search(/(了解|好的|知道|Got It)/) != -1) {
                element.click();
                if (isHidden(element)) { continue; }
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

    async function removeErrorWindowsMultiTimes() {
        for (const times of Array(15).keys()) {
            await sleep(200);
            if (removeErrorWindows()) {
                logger.info(`remove error window used time: ${(times + 1) * 0.2}`);
                break;
            };
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
            onerror: function (error) {
                alert(`${url}\n请求错误，本地服务未运行，请查看使用说明。\nhttps://github.com/kjtsune/embyToLocalPlayer`);
                console.error('请求错误:', error);
            }
        });
        logger.info(path, data);
    }

    let serverName = null;
    let episodesInfoCache = []; // ['type:[Episodes|NextUp|Items]', resp]
    let episodesInfoRe = /\/Episodes\?IsVirtual|\/NextUp\?Series|\/Items\?ParentId=\w+&Filters=IsNotFolder&Recursive=true/; // Items已排除播放列表
    // 点击位置：Episodes 继续观看，如果是即将观看，可能只有一集的信息 | NextUp 新播放或媒体库播放 | Items 季播放。 只有 Episodes 返回所有集的数据。
    let playlistInfoCache = null;
    let resumeRawInfoCache = null;
    let resumePlaybakCache = {};
    let resumeItemDataCache = {};
    let allPlaybackCache = {};
    let allItemDataCache = {};

    let metadataChangeRe = /\/MetadataEditor|\/Refresh\?/;
    let metadataMayChange = false;

    function cleanOptionalCache() {
        resumeRawInfoCache = null;
        resumePlaybakCache = {};
        resumeItemDataCache = {};
        allPlaybackCache = {};
        allItemDataCache = {};
        episodesInfoCache = []
    }

    function throttle(fn, delay) {
        let lastTime = 0;
        return function (...args) {
            const now = Date.now();
            if (now - lastTime >= delay) {
                lastTime = now;
                fn.apply(this, args);
            }
        };
    }

    let addOpenFolderElement = throttle(_addOpenFolderElement, 100);

    async function _addOpenFolderElement(itemId) {
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

        let itemData = (itemId in allItemDataCache) ? allItemDataCache[itemId] : null
        let strmFile = (full_path.startsWith('http')) ? itemData?.Path : null

        let openButtonHtml = `<a id="openFolderButton" is="emby-linkbutton" class="raised item-tag-button 
        nobackdropfilter emby-button" ><i class="md-icon button-icon button-icon-left">link</i>Open Folder</a>`
        pathDiv.insertAdjacentHTML('beforebegin', openButtonHtml);
        let btn = mediaSources.querySelector('a#openFolderButton');
        if (strmFile) {
            pathDiv.innerHTML = pathDiv.innerHTML + '<br>' + strmFile;
            full_path = strmFile; // emby 会把 strm 内的链接当路径展示
        }
        btn.addEventListener('click', () => {
            logger.info(full_path);
            sendDataToLocalServer({ full_path: full_path }, 'openFolder');
        });
    }

    async function addFileNameElement(resp) {
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
        if (_pathDiv.id == 'addFileNameElement') return;
        let isAdmin = !/\d{4}\/\d+\/\d+/.test(_pathDiv.textContent); // 非管理员只有包含添加日期的文件类型 div
        let isStrm = _pathDiv.textContent.startsWith('http');
        if (isAdmin) {
            if (!isStrm) { return; }
            pathDivs = pathDivs.filter((_, index) => index % 2 === 0); // 管理员一个文件同时有路径和文件类型两个 div
        }

        let sources = await resp.clone().json();
        sources = sources.MediaSources;
        for (let index = 0; index < pathDivs.length; index++) {
            const pathDiv = pathDivs[index];
            let fileName = sources[index].Name; // 多版本的话，是版本名。
            let filePath = sources[index].Path;
            let strmFile = filePath.startsWith('http');
            if (!strmFile) {
                fileName = filePath.split('\\').pop().split('/').pop();
                fileName = (config.crackFullPath && !isAdmin) ? filePath : fileName;
            }
            let fileDiv = `<div id="addFileNameElement">${fileName}</div> `
            if (strmFile && (!isAdmin && config.crackFullPath)) {
                fileDiv = `<div id="addFileNameElement">${fileName}<br>${filePath}</div> `
            }
            pathDiv.insertAdjacentHTML('beforebegin', fileDiv);
        }
    }

    function makeItemIdCorrect(itemId) {
        if (serverName !== 'emby') { return itemId; }
        if (!resumeRawInfoCache || !episodesInfoCache) { return itemId; }
        let resumeIds = resumeRawInfoCache.map(item => item.Id);
        if (resumeIds.includes(itemId)) { return itemId; }
        let pageId = window.location.href.match(/\/item\?id=(\d+)/)?.[1];
        if (resumeIds.includes(pageId) && itemId == episodesInfoCache[0].Id) {
            // 解决从继续观看进入集详情页时，并非播放第一集，却请求首集视频文件信息导致无法播放。
            // 手动解决方法：从下方集卡片点击播放，或从集卡片再次进入集详情页后播放。
            // 本函数的副作用：集详情页底部的第一集卡片点播放按钮会播放当前集。
            // 副作用解决办法：再点击一次，或者点第一集卡片进入详情页后再播放。不过一般也不怎么会回头看第一集。
            return pageId;

        } else if (window.location.href.match(/serverId=/)) {
            return itemId; // 仅处理首页继续观看和集详情页，其他页面忽略。
        }
        let correctSeaId = episodesInfoCache.find(item => item.Id == itemId)?.SeasonId;
        let correctItemId = resumeRawInfoCache.find(item => item.SeasonId == correctSeaId)?.Id;
        if (correctSeaId && correctItemId) {
            logger.info(`makeItemIdCorrect, old=${itemId}, new=${correctItemId}`)
            return correctItemId;
        }
        return itemId;
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

    async function apiClientGetWithCache(itemId, cacheList, funName) {
        for (const cache of cacheList) {
            if (itemId in cache) {
                logger.info(`HIT ${funName} itemId=${itemId}`)
                return cache[itemId];
            }
        }
        logger.info(`MISS ${funName} itemId=${itemId}`)
        let resInfo;
        switch (funName) {
            case 'getPlaybackInfo':
                resInfo = await ApiClient.getPlaybackInfo(itemId);
                break;
            case 'getItem':
                resInfo = await ApiClient.getItem(ApiClient._serverInfo.UserId, itemId);
                break;
            default:
                break;
        }
        for (const cache of cacheList) {
            cache[itemId] = resInfo;
        }
        return resInfo;
    }

    async function getPlaybackWithCace(itemId) {
        return apiClientGetWithCache(itemId, [resumePlaybakCache, allPlaybackCache], 'getPlaybackInfo');
    }

    async function getItemInfoWithCace(itemId) {
        return apiClientGetWithCache(itemId, [resumeItemDataCache, allItemDataCache], 'getItem');
    }

    async function dealWithPlaybakInfo(raw_url, url, options) {
        console.time('dealWithPlaybakInfo');
        let rawId = url.match(/\/Items\/(\w+)\/PlaybackInfo/)[1];
        episodesInfoCache = episodesInfoCache[0] ? episodesInfoCache[1].clone() : null;
        let itemId = rawId;
        let [playbackData, mainEpInfo, episodesInfoData] = await Promise.all([
            getPlaybackWithCace(itemId), // originFetch(raw_url, request), 可能会 NoCompatibleStream
            getItemInfoWithCace(itemId),
            episodesInfoCache?.json(),
        ]);
        console.timeEnd('dealWithPlaybakInfo');
        episodesInfoData = (episodesInfoData && episodesInfoData.Items) ? episodesInfoData.Items : null;
        episodesInfoCache = episodesInfoData;
        let correctId = makeItemIdCorrect(itemId);
        url = url.replace(`/${rawId}/`, `/${correctId}/`)
        if (itemId != correctId) {
            itemId = correctId;
            [playbackData, mainEpInfo] = await Promise.all([
                getPlaybackWithCace(itemId),
                getItemInfoWithCace(itemId),
            ]);
            let startPos = mainEpInfo.UserData.PlaybackPositionTicks;
            url = url.replace('StartTimeTicks=0', `StartTimeTicks=${startPos}`);
        }
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
        // resumeInfoCache = null;
        logger.info(extraData);
        if (mainEpInfo?.Type == 'Trailer') {
            alert('etlp: Does not support Trailers plugin. Please disable it.');
            return false;
        }
        let notBackdrop = Boolean(playbackData.MediaSources[0].Path.search(/\Wbackdrop/i) == -1);
        if (notBackdrop) {
            let _req = options ? options : raw_url;
            embyToLocalPlayer(url, _req, playbackData, extraData);
            return true;
        }
        return false;
    }

    async function cacheResumeItemInfo() {
        let inInit = !myBool(resumeRawInfoCache);
        let resumeIds;
        let storageKey = 'etlpResumeIds'
        if (inInit) {
            resumeIds = localStorage.getItem(storageKey)
            if (resumeIds) {
                resumeIds = JSON.parse(resumeIds);
            } else {
                return
            }
        } else {
            resumeIds = resumeRawInfoCache.slice(0, 5).map(item => item.Id);
            localStorage.setItem(storageKey, JSON.stringify(resumeIds));
        }

        for (let [globalCache, getFun] of [[resumePlaybakCache, getPlaybackWithCace], [resumeItemDataCache, getItemInfoWithCace]]) {
            let cacheDataAcc = {};
            if (myBool(globalCache)) {
                cacheDataAcc = globalCache;
                resumeIds = resumeIds.filter(id => !(id in globalCache));
                if (resumeIds.length == 0) { return; }
            }
            let itemInfoList = await Promise.all(
                resumeIds.map(id => getFun(id))
            )
            globalCache = itemInfoList.reduce((acc, result, index) => {
                acc[resumeIds[index]] = result;
                return acc;
            }, cacheDataAcc);
        }

    }

    async function cloneAndCacheFetch(resp, key, cache) {
        try {
            const data = await resp.clone().json();
            cache[key] = data;
            return data;
        } catch (_error) {
            // pass
        }
    }

    let itemInfoRe = /Items\/(\w+)\?/;

    unsafeWindow.fetch = async (url, options) => {
        const raw_url = url;
        let urlType = typeof url;
        if (urlType != 'string') {
            url = raw_url.url;
        }
        if (serverName === null) {
            serverName = typeof ApiClient === 'undefined' ? null : ApiClient._appName.split(' ')[0].toLowerCase();
        } else {
            if (typeof ApiClient != 'undefined' && ApiClient._deviceName != 'embyToLocalPlayer' && localStorage.getItem('webPlayerEnable') != 'true') {
                ApiClient._deviceName = 'embyToLocalPlayer'
                cacheResumeItemInfo();
            }
        }
        if (metadataMayChange && url.includes('Items')) {
            if (url.includes('reqformat') && !url.includes('fields')) {
                cleanOptionalCache();
                metadataMayChange = false;
                logger.info('cleanOptionalCache by metadataMayChange')
            }
        }
        // 适配播放列表及媒体库的全部播放、随机播放。限电影及音乐视频。
        if (url.includes('Items?') && (url.includes('Limit=300') || url.includes('Limit=1000'))) {
            let _resp = await originFetch(raw_url, options);
            if (serverName == 'emby') {
                await ApiClient._userViewsPromise?.then(result => {
                    let viewsItems = result.Items;
                    let viewsIds = [];
                    viewsItems.forEach(item => {
                        viewsIds.push(item.Id);
                    });
                    let viewsRegex = viewsIds.join('|');
                    viewsRegex = `ParentId=(${viewsRegex})`
                    if (!RegExp(viewsRegex).test(url)) { // 点击季播放美化标题所需，并非媒体库随机播放。
                        episodesInfoCache = ['Items', _resp.clone()]
                        logger.info('episodesInfoCache', episodesInfoCache);
                        logger.info('viewsRegex', viewsRegex);
                        return _resp;
                    }
                }).catch(error => {
                    console.error('Error occurred: ', error);
                });
            }

            playlistInfoCache = null;
            let _resd = await _resp.clone().json();
            if (!_resd.Items[0]) {
                logger.error('playlist is empty, skip');
                return _resp;
            }
            if (['Movie', 'MusicVideo'].includes(_resd.Items[0].Type)) {
                playlistInfoCache = _resd
                logger.info('playlistInfoCache', playlistInfoCache);
            }
            return _resp
        }
        // 获取各集标题等，仅用于美化标题，放后面避免误拦截首页右键媒体库随机播放数据。
        let _epMatch = url.match(episodesInfoRe);
        if (_epMatch) {
            _epMatch = _epMatch[0].split(['?'])[0].substring(1); // Episodes|NextUp|Items
            let _resp = await originFetch(raw_url, options);
            episodesInfoCache = [_epMatch, _resp.clone()]
            logger.info('episodesInfoCache', episodesInfoCache);
            return _resp
        }
        if (url.includes('Items/Resume') && url.includes('MediaTypes=Video')) {
            let _resp = await originFetch(raw_url, options);
            let _resd = await _resp.clone().json();
            resumeRawInfoCache = _resd.Items;
            cacheResumeItemInfo();
            logger.info('resumeRawInfoCache', resumeRawInfoCache);
            return _resp
        }
        // 缓存 itemInfo ，可能匹配到 Items/Resume，故放后面。
        if (url.match(itemInfoRe)) {
            let itemId = url.match(itemInfoRe)[1];
            let resp = await originFetch(raw_url, options);
            cloneAndCacheFetch(resp, itemId, allItemDataCache);
            return resp;
        }
        try {
            if (url.indexOf('/PlaybackInfo?UserId') != -1) {
                if (url.indexOf('IsPlayback=true') != -1 && localStorage.getItem('webPlayerEnable') != 'true') {
                    if (await dealWithPlaybakInfo(raw_url, url, options)) { return; } // Emby
                } else {
                    let itemId = url.match(/\/Items\/(\w+)\/PlaybackInfo/)[1];
                    let resp = await originFetch(raw_url, options);
                    addFileNameElement(resp.clone()); // itemId data 不包含多版本的文件信息，故用不到
                    addOpenFolderElement(itemId);
                    cloneAndCacheFetch(resp.clone(), itemId, allPlaybackCache);
                    return resp;
                }
            } else if (url.indexOf('/Playing/Stopped') != -1 && localStorage.getItem('webPlayerEnable') != 'true') {
                return
            }
        } catch (error) {
            logger.error(error, raw_url, url);
            removeErrorWindowsMultiTimes();
            return
        }

        if (url.match(metadataChangeRe)) {
            if (url.includes('MetadataEditor')) {
                metadataMayChange = true;
            } else {
                cleanOptionalCache();
                logger.info('cleanOptionalCache by Refresh')
            }
        }
        return originFetch(raw_url, options);
    }

    function initXMLHttpRequest() {

        const originOpen = XMLHttpRequest.prototype.open;
        const originSend = XMLHttpRequest.prototype.send;
        const originSetHeader = XMLHttpRequest.prototype.setRequestHeader;

        XMLHttpRequest.prototype.setRequestHeader = function (header, value) {
            this._headers[header] = value;
            return originSetHeader.apply(this, arguments);
        }

        XMLHttpRequest.prototype.open = function (method, url) {
            this._method = method;
            this._url = url;
            this._headers = {};

            if (serverName === null && this._url.indexOf('X-Plex-Product') != -1) { serverName = 'plex' };
            let catchPlex = (serverName == 'plex' && this._url.indexOf('playQueues?type=video') != -1)
            if (catchPlex && localStorage.getItem('webPlayerEnable') != 'true') { // Plex
                fetch(this._url, {
                    method: this._method,
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
                            playbackUrl: this._url,
                            mountDiskEnable: localStorage.getItem('mountDiskEnable'),
                            extraData: extraData,
                        };
                        sendDataToLocalServer(data, 'plexToLocalPlayer');
                    });
                return;
            }
            return originOpen.apply(this, arguments);
        }

        XMLHttpRequest.prototype.send = function (body) {

            let catchJellyfin = (this._method === 'POST' && this._url.endsWith('PlaybackInfo'))
            if (catchJellyfin && localStorage.getItem('webPlayerEnable') != 'true') { // Jellyfin
                let pbUrl = this._url;
                body = JSON.parse(body);
                let _body = {};
                ['MediaSourceId', 'StartTimeTicks', 'UserId'].forEach(key => {
                    _body[key] = body[key]
                });
                let query = new URLSearchParams(_body).toString();
                pbUrl = `${pbUrl}?${query}`
                let options = {
                    headers: this._headers,
                };
                dealWithPlaybakInfo(pbUrl, pbUrl, options);
                return;
            }
            originSend.apply(this, arguments);
        }
    }

    initXMLHttpRequest();

    setModeSwitchMenu('webPlayerEnable', '脚本在当前服务器 已', '', '启用', '禁用', '启用');
    setModeSwitchMenu('mountDiskEnable', '读取硬盘模式已经 ');

    _init_config_main();
})();