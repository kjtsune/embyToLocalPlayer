// ==UserScript==
// @name         embyEverywhere
// @description  add Emby search result in many sites。eg: imdb.com trakt.tv tmdb tvdb
// @description:zh-CN   在许多网站上添加 Emby 跳转链接。例如: bgm.tv douban imdb tmdb tvdb trakt
// @namespace    https://github.com/kjtsune/embyToLocalPlayer
// @version      2025.11.04
// @author       Kjtsune
// @icon         https://www.google.com/s2/favicons?sz=64&domain=emby.media
// @match        https://bgm.tv/subject/*
// @match        https://movie.douban.com/subject/*
// @match        https://www.imdb.com/title/*
// @match        https://www.themoviedb.org/tv/*
// @match        https://www.themoviedb.org/movie/*
// @match        https://trakt.tv/movies/*
// @match        https://trakt.tv/shows/*
// @match        https://thetvdb.com/series/*
// @match        https://www.google.com/search*
// @match        *://*/web/index.html*
// @match        *://*/*/web/index.html*
// @grant        GM_xmlhttpRequest
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_deleteValue
// @grant        GM_registerMenuCommand
// @connect      *
// @require      https://fastly.jsdelivr.net/gh/kjtsune/UserScripts@a4c9aeba777fdf8ca50e955571e054dca6d1af49/lib/basic-tool.js
// @require      https://fastly.jsdelivr.net/gh/kjtsune/UserScripts@a4c9aeba777fdf8ca50e955571e054dca6d1af49/lib/my-storage.js
// @require      https://fastly.jsdelivr.net/gh/kjtsune/UserScripts@9b2ee646bbf527cfe17150b5be3ad4c420d9071a/lib/my-apis.js
// @license      MIT
// ==/UserScript==

'use strict';

/*global ApiClient*/

let _false = false;
if (_false) {
    import('./lib/basic-tool.js');
    /*global MyLogger myBool */
    import('./lib/my-storage.js');
    /*global MyStorage */
    import('./lib/my-apis.js');
    /*global BangumiApi EmbyApi TraktApi TmdbApi DoubanApi */ // BaseApi
}

// settings start

let embyServerDatas = [
    {
        name: 'NAS',
        url: 'http://192.168.1.1:8096',
        userName: 'guest',
        passWord: 'pw',
        apiKey: '', // 如果填了用户名和密码，apiKey 可以不用。
    },
    {
        name: '公益服A',
        url: 'https://free.lan:443', // https 端口也要填。
        userName: '',
        passWord: '',
        apiKey: '8cg0aqtytc7nhvwgycjqiw2kobgne2jk', // 也可以只填 apiKey
    },
    {
        name: '公益服B', // 有几个服就填几份了。
        url: 'http://example.local:80',
        userName: '',
        passWord: '',
        apiKey: '',
    },
]

let config = {
    // saveSettigs 的 false 改成 true 后会将上方配置保存到油猴插件设置存储里。避免脚本升级时丢失配置。
    // 存储里的配置会比上方手写的配置优先。所以若更新配置，记得改成 true 覆盖旧配置。
    // 手动清空存储的方法：油猴插件 -> 本脚本 -> 编辑 -> 存储 -> 清空内容（上下大括号{}需要保留）/ 或只删除 script|saveStings 那行。
    // 自己也备份一下上方的配置，会比较稳妥。
    saveSettigs: false,
    logLevel: 2,
};

let logger = new MyLogger(config)

// 以下为测试功能，不用管他

let tmdbToken = '';
(() => {
    let settsingDb = new MyStorage('script|saveStings', undefined, undefined, true);
    if (tmdbToken) {
        settsingDb.set('tmdbToken', tmdbToken);
        return;
    }
    if (settsingDb.get('tmdbToken')) {
        tmdbToken = settsingDb.get('tmdbToken');
    }
})()

let traktTkoenObj, traktSettings;
// traktTkoenObj = {
//     'access_token': '',
//     'token_type': 'Bearer',
//     'expires_in': Number,
//     'refresh_token': '',
//     'scope': 'public',
//     'created_at': Number
// }
// traktSettings = {
//     userName: '',
//     clientId: '',
//     clientSecret: '',
//     traktTkoenObj: traktTkoenObj,
// }
// 参考 etlp 脚本里 trakt sync 功能。
// traktTkoenObj 是其生成的 trakt_token.json

// settings end

function stringify(value) {
    if (value !== null && typeof value === 'object') {
        return JSON.stringify(value)
    }

    return value;
}

function _trimCharacter(str, char) {
    const regex = new RegExp(`^[${char}]+|[${char}]+$`, 'g');
    return str.replace(regex, '');
}

function storageUndefinedClear() {
    for (let i in localStorage) {
        if (i.includes('undefined')) {
            console.log('remove', i);
            localStorage.removeItem(i);
        }
    }
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

function settingsSaverBase(key, value, force = false) {
    let overwrite = config.saveSettigs || force;
    let settsingDb = new MyStorage('script|saveStings', undefined, undefined, true);
    if (overwrite && myBool(value)) {
        settsingDb.set(key, value);
    } else {
        let settingsOld = settsingDb.get(key);
        if (settingsOld) {
            value = settingsOld;
        }
    }
    return value;
}

async function doubanPlayedByTrakt() {
    if (window.location.host != 'movie.douban.com') {
        return;
    }

    traktSettings = settingsSaverBase('traktSettings', traktSettings, false);
    traktSettings = (typeof (traktSettings) == 'string') ? JSON.parse(traktSettings) : traktSettings;

    if (!traktSettings) {
        return;
    }
    let userName = traktSettings.userName;
    let clientId = traktSettings.clientId;
    let clientSecret = traktSettings.clientSecret;
    traktTkoenObj = traktSettings.traktTkoenObj;
    let traktApi = new TraktApi(userName, clientId, clientSecret, traktTkoenObj);
    let newToken = await traktApi.refreshToken();
    if (newToken) {
        traktSettings.traktTkoenObj = newToken;
        settingsSaverBase('traktSettings', traktSettings, true);
    }
    let tmdbApi = new TmdbApi(tmdbToken);

    let imdbA = document.querySelector('#info > a[href*="imdb.com/title"]');
    if (!imdbA) {
        return;
    }
    let imdbId = imdbA.href.split('/').at(-1);

    let imdbWatchedDb = new MyStorage('imdb|watched', 7);
    let imdbTraktIdsDb = new MyStorage('imdb|trakt|ids');
    let imdbWatched = imdbWatchedDb.get(imdbId);
    let watchedState, watchedData, tkIds;
    tkIds = imdbTraktIdsDb.get(imdbId);
    if (imdbWatched) {
        [watchedState, watchedData] = [true, {}]
    } else {
        if (!myBool(tkIds)) {
            let tmInfo = await tmdbApi.findById('imdb', imdbId);
            if (myBool(tmInfo)) {
                let tmType = tmInfo.media_type;
                tmType = {'tv': 'show'}[tmType] || tmType;
                let tmId = tmInfo.id;
                tkIds = await traktApi.idLookup('tmdb', tmId, tmType);
            } else {
                tkIds = await traktApi.idLookup('imdb', imdbId);
            }
            tkIds = tkIds[0]
            imdbTraktIdsDb.set(imdbId, tkIds)
        }
        if (!myBool(tkIds)) {
            logger.error('traktApi.idLookup not result, skip mark played');
            return;
        }

        logger.info(`trakt ${stringify(tkIds)}`);
        [watchedState, watchedData] = await traktApi.checkIsWatched(tkIds, true);
        if (watchedState) {
            imdbWatchedDb.set(imdbId, true);
        }
    }
    if (myBool(tkIds)) {
        let tmdbType = (tkIds.type == 'movie') ? 'movie' : 'tv';
        let tmdbId = tkIds[tkIds.type].ids.tmdb;
        let tmdbHtml = `<a id="tmdbLink" href="https://www.themoviedb.org/${tmdbType}/${tmdbId}" target="_blank">  tmdb</a>`
        if (tmdbId) {
            imdbA.insertAdjacentHTML('afterend', tmdbHtml);
        }
    }
    logger.info(`trakt watchedState ${stringify(watchedState)}`);
    let watchedEmoji = (watchedState) ? '✔️' : '✖️';
    let watchedStr = ''
    if (!watchedState && watchedData.aired) {
        watchedStr = ` ${((watchedData.completed / watchedData.aired) * 100).toFixed(0)}%`
    }
    imdbA.previousElementSibling.insertAdjacentHTML('beforebegin', `<span class="pl">看过:</span>${watchedStr} ${watchedEmoji}<br>`);
}

class ProviderIdsAdder {
    constructor({
                    anchorSelector = '',
                    inputId = ['imdb', 'tt1234'],
                    targetProviders = ['tmdb'],
                    adderMethod = ProviderIdsAdder.prototype.linkAdder.name,
                }) {
        this.anchorSelector = anchorSelector;
        this.inputIdName = inputId[0];
        this.inputIdValue = inputId[1];
        this.targetProviders = targetProviders;
        this.targetIds = [];
        this.adderMethod = adderMethod;
    }

    async mainAdder() {
        if (!tmdbToken) {
            return;
        }
        let tmInfo;
        for (const tProvName of this.targetProviders) {
            let tProvDb = new MyStorage(`${this.inputIdName}|${tProvName}`);
            let tProvValue = tProvDb.get(this.inputIdValue);
            let tmdbApi = new TmdbApi(tmdbToken);
            if (!myBool(tProvValue)) {
                if (!myBool(tmInfo)) {
                    if (this.inputIdName == 'tmdb') {
                        tmInfo = await tmdbApi.tmdbExternalIds(this.inputIdValue);
                    } else {
                        tmInfo = await tmdbApi.findById(this.inputIdName, this.inputIdValue);
                    }
                }
                if (myBool(tmInfo)) {
                    let tmdbId = (this.inputIdName == 'tmdb') ? this.inputIdValue : `${tmInfo.media_type}/${tmInfo.id}`;
                    if (tProvName == 'tmdb') {
                        tProvValue = tmdbId;
                    }
                    if (['imdb', 'tvdb'].includes(tProvName)) {
                        for (const tName of ['imdb', 'tvdb']) {
                            let _key = `${tName}_id`
                            let _value = tmInfo[_key];
                            if (_value) {
                                let _Db = new MyStorage(`${this.inputIdName}|${tName}`);
                                _Db.set(this.inputIdValue, _value);
                            }
                            if (tName == tProvName) {
                                tProvValue = _value;
                            }
                        }
                    }
                    if (tProvName == 'douban') {
                        let _imdbId;
                        if (this.inputIdName == 'imdb') {
                            _imdbId = this.inputIdValue;
                        } else {
                            let _imdbDb = new MyStorage('tmdb|imdb');
                            _imdbId = _imdbDb.get(tmdbId);
                        }
                        if (_imdbId) {
                            let doubanApi = new DoubanApi();
                            let doubanId = await doubanApi.getDoubanIdWithStorage(MyStorage, _imdbId);
                            if (doubanId && doubanId != '_') {
                                tProvValue = doubanId;
                            }
                        }
                    }
                }

                if (myBool(tProvValue)) {
                    tProvDb.set(this.inputIdValue, tProvValue);
                }

            }
            if (myBool(tProvValue)) {
                this.targetIds.push(tProvValue);
            } else {
                this.targetIds.push(null);
            }

        }

        this[this.adderMethod]();

    }

    linkAdder(position = 'beforeend', innerHtml = '', preHtml = '', sufHtml = '') { // beforebegin beforeend
        let anchor = document.querySelector(this.anchorSelector);
        this.targetProviders.forEach((tProvName, index) => {
            let tProvValue = this.targetIds[index];
            if (!tProvValue) {
                return;
            }
            let hrefMap = {
                'imdb': `https://www.imdb.com/title/${tProvValue}`,
                'tmdb': `https://www.themoviedb.org/${tProvValue}`,
                'tvdb': `https://thetvdb.com/?tab=series&id=${tProvValue}`,
                'douban': `https://movie.douban.com/subject/${tProvValue}`
            }
            let href = hrefMap[tProvName] || 'hrefMapNotMatch';
            let idHtml = `<a id="${tProvName}Link" add-by="providerIdsAdder" ${innerHtml} href="${href}" target="_blank"> ${tProvName}</a>`
            idHtml = `${preHtml}${idHtml}${sufHtml}`
            anchor.insertAdjacentHTML(position, idHtml);
        });
    }

    imdbPageAdder() {
        let innerHtml = 'class= "ipc-link ipc-link--baseAlt ipc-link--inherit-color"'
        let preHtml = '<li role="presentation" class="ipc-inline-list__item">'
        let sufHtml = '</li>'
        this.linkAdder('beforeend', innerHtml, preHtml, sufHtml)
    }

    _createGoogleProvEle(templateElement, provUrl, provScore, provName) {
        const newElement = templateElement.cloneNode(true);
        newElement.setAttribute('href', provUrl);
        const pingAttr = newElement.getAttribute('ping');
        if (pingAttr) {
            const newPing = pingAttr.replace(
                /url=https?:\/\/[^&]+/,
                `url=${encodeURIComponent(provUrl)}`
            );
            newElement.setAttribute('ping', newPing);
        }
        const directSpans = Array.from(newElement.querySelectorAll(':scope > span'));
        directSpans.forEach(span => {
            const text = span.textContent.trim();
            // 判断是评分 span（包含数字和斜杠）
            if (/^\d+(\.\d+)?\/\d+$/.test(text)) {
                span.textContent = provScore;
            } else if (span.hasAttribute('title')) {
                span.textContent = provName;
                span.setAttribute('title', provName);
            }
            // 跳过分隔符 span（内容是 · 或其他单字符）
            else if (text.length <= 3 && !/[a-zA-Z0-9]/.test(text)) {
                // 保持不变
            }
        });
        const descriptionSpan = newElement.querySelector('div > div > span');
        if (descriptionSpan) {
            descriptionSpan.textContent = `Scored ${provScore} on ${provName}.`;
        }
        return newElement;
    }

    googlePageAdder() {
        let templateEl = document.querySelector(this.anchorSelector);
        if (!templateEl) return;

        this.targetProviders.forEach((tProvName, index) => {
            let tProvValue = this.targetIds[index];
            if (!tProvValue) {
                return;
            }
            let hrefMap = {
                'imdb': `https://www.imdb.com/title/${tProvValue}`,
                'tmdb': `https://www.themoviedb.org/${tProvValue}`,
                'tvdb': `https://thetvdb.com/?tab=series&id=${tProvValue}`,
                'douban': `https://movie.douban.com/subject/${tProvValue}`
            }
            let href = hrefMap[tProvName] || 'hrefMapNotMatch';
            let score = this.scores?.[tProvName] || ' ';
            const newEl = this._createGoogleProvEle(
                templateEl,
                href,
                score,
                tProvName
            );

            newEl.setAttribute('id', `${tProvName}Link`);
            newEl.setAttribute('add-by', 'providerIdsAdder');

            templateEl.parentNode.insertBefore(newEl, templateEl.nextSibling);
            // 更新 templateEl 为新插入的元素，这样下一个会插在它后面
            templateEl = newEl;
        });
    }

    tmdbPageAdder() {
        let innerHtml = 'class= "ipc-link ipc-link--baseAlt ipc-link--inherit-color"'
        let preHtml = '<span class="genres">'
        let sufHtml = '</li>'
        this.linkAdder('beforeend', innerHtml, preHtml, sufHtml)
    }

}

class EmbyLinkAdder {
    constructor({
                    titleSelector = '',
                    searchMethod = 'searchByName',
                    searchArgs = [],
                    adderMethod = EmbyLinkAdder.prototype.titleAdder.name,
                }) {
        this.titleSelector = titleSelector;
        this.searchMethod = searchMethod;
        this.searchArgs = searchArgs;
        this.addedElements = [];
        this.adderMethod = adderMethod;

    }

    embyIconAdder(embyLink) {
        if (document.querySelector('img[add-by="embyEverywhere"]')) {
            return;
        }
        let iconBase64 = 'PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0idXRmLTgiPz48IS0tIFVwbG9hZGVkIHRvOiBTVkcgUmVwbywgd3d3LnN2Z3JlcG8uY29tLCBHZW5lcmF0b3I6IFNWRyBSZXBvIE1peGVyIFRvb2xzIC0tPgo8c3ZnIGZpbGw9IiM0Q0FGNTAiIHdpZHRoPSI4MDBweCIgaGVpZ2h0PSI4MDBweCIgdmlld0JveD0iMCAwIDI0IDI0IiByb2xlPSJpbWciIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHRpdGxlPkVtYnkgaWNvbjwvdGl0bGU+PHBhdGggZD0iTTExLjA0MSAwYy0uMDA3IDAtMS40NTYgMS40My0zLjIxOSAzLjE3Nkw0LjYxNSA2LjM1MmwuNTEyLjUxMy41MTIuNTEyLTIuODE5IDIuNzkxTDAgMTIuOTYxbDEuODMgMS44NDhjMS4wMDYgMS4wMTYgMi40MzggMi40NiAzLjE4MiAzLjIwOWwxLjM1MSAxLjM1OS41MDgtLjQ5NmMuMjgtLjI3My41MTUtLjQ5OC41MjQtLjQ5OC4wMDggMCAxLjI2NiAxLjI2NCAyLjc5NCAyLjgwOEwxMi45NyAyNGwuMTg3LS4xODJjLjIzLS4yMjUgNS4wMDctNC45NSA1LjcxNy01LjY1NmwuNTItLjUxNi0uNTAyLS41MTNjLS4yNzYtLjI4Mi0uNS0uNTItLjQ5Ni0uNTMuMDAzLS4wMDkgMS4yNjQtMS4yNiAyLjgwMi0yLjc4MyAxLjUzOC0xLjUyMiAyLjgtMi43NzYgMi44MDMtMi43ODUuMDA1LS4wMTItMy42MTctMy42ODQtNi4xMDctNi4xOTNMMTcuNjUgNC42bC0uNTA1LjUwNWMtLjI3OS4yNzgtLjUxNy41MDEtLjUzLjQ5Ny0uMDEzLS4wMDUtMS4yNy0xLjI2Ny0yLjc5My0yLjgwNUE0NDkuNjU1IDQ0OS42NTUgMCAwMDExLjA0MSAwek05LjIyMyA3LjM2N2MuMDkxLjAzOCA3Ljk1MSA0LjYwOCA3Ljk1NyA0LjYyNy4wMDMuMDEzLTEuNzgxIDEuMDU2LTMuOTY1IDIuMzJhOTk5Ljg5OCA5OTkuODk4IDAgMDEtMy45OTYgMi4zMDdjLS4wMTkuMDA2LS4wMjYtMS4yNjYtLjAyNi00LjYyOSAwLTMuNy4wMDctNC42MzQuMDMtNC42MjVaIi8+PC9zdmc+'
        let iconSrc = 'data:image/svg+xml;base64,' + iconBase64;
        // let linkWidth = embyLink.offsetWidth;
        let linkHeight = embyLink.offsetHeight;
        let style = `style="display: inline-block; vertical-align: middle;" width="${linkHeight}"`
        let embyIcon = `<img ${style} add-by="embyEverywhere" src="${iconSrc}">`;
        embyLink.insertAdjacentHTML('beforebegin', embyIcon);
    }

    async mainAdder() {
        let searchPromises = [];
        if (this.searchMethod == 'searchByName' && (!this.searchArgs[0])) {
            return;
        }
        for (const embyServer of embyServerDatas) {
            if (document.getElementById(embyServer.name)) {
                continue;
            }
            let embyApi = new EmbyApi(embyServer.url, embyServer.apiKey, embyServer.userId, embyServer.userName, embyServer.passWord);
            searchPromises.push(
                (async () => {
                    let searchData;
                    try {
                        await embyApi.checkTokenAlive(MyStorage);
                        searchData = await embyApi[this.searchMethod](...this.searchArgs);
                    } catch (_error) {
                        let resData = {'name': embyServer.name, 'url': false};
                        this[this.adderMethod](resData);
                        logger.error(_error);
                        return null;
                    }
                    logger.info(`search by ${embyServer.name} ${this.searchMethod} ${stringify(this.searchArgs)}`)
                    if (!myBool(searchData)) {
                        logger.info(`${embyServer.name} not result  ${stringify(this.searchArgs)} ${stringify(searchData)}`);
                        return null;
                    } else {
                        let results = [];
                        for (const searchRes of searchData.slice(0, 3)) {
                            let itemUrl = embyApi.itemObjToUrl(searchRes);
                            let resData = {'name': embyServer.name, 'url': itemUrl};
                            this[this.adderMethod](resData);
                            this.addedElements.push(resData);
                            results.push(resData);
                        }
                        return results;
                    }
                })()
            );
        }
        await Promise.all(searchPromises);
        if (myBool(this.addedElements)) {
            let embyLink = document.querySelector('a[add-by="embyEverywhere"]');
            this.embyIconAdder(embyLink);
        }
        return this.addedElements;
    }

    titleAdder(data, extHtml = '', position = 'beforebegin', parentLevel = 0) { // beforeend
        let title = getVisibleElement(document.querySelectorAll(this.titleSelector));
        if (parentLevel > 0) {
            for (let i = 0; i < parentLevel; i++) {
                if (title.parentElement) {
                    title = title.parentElement;
                } else {
                    break; // 防止超出 DOM 层级
                }
            }
        }
        let elementId = `${data.name}`
        let linkHtml = `<a id=${elementId} target="_blank" add-by="embyEverywhere"`
        let embyLink = `${linkHtml} href="${data.url}"${extHtml}>${data.name},</a>`;
        if (!data.url) {
            embyLink = `${linkHtml}${extHtml}>${data.name}🚧,</a>`;
        }
        title.insertAdjacentHTML(position, embyLink);
    }

    titleFatherAdder(data) {
        this.titleAdder(data, '', 'beforebegin', 2);
    }

    whiteTitleAdder(data) {
        // 这个 class 是 imdb 的，不过应该没副作用。
        let extHtml = ' class="ipc-link--baseAlt" style="color: white;"';
        this.titleAdder(data, extHtml, 'beforebegin'); // afterend
    }

    beforeendTitleAdder(data) {
        this.titleAdder(data, '', 'beforeend');
    }

    notResultTitleAdder(position = 'beforebegin') {
        let titleElement = document.querySelector(this.titleSelector);
        let htmlStr = '<span add-by="embyEverywhere" class="pl"> Null</span>';
        titleElement.insertAdjacentHTML(position, htmlStr);
        let embyLink = document.querySelector('span[add-by="embyEverywhere"]');
        this.embyIconAdder(embyLink);
    }
}

async function bgmSubjectPage(asTV = false) {
    let bgmAllowDomains = ['bgm.tv', 'bangumi.tv', 'chii.in'];
    let curDomain = window.location.hostname;
    if (!bgmAllowDomains.includes(curDomain)) {
        return;
    }
    let allowTypes = ['v:Movie',]
    let headerSubject = document.getElementById('headerSubject');
    let subjectType = (headerSubject) ? headerSubject.getAttribute('typeof') : 'not bgm page';
    if (!allowTypes.includes(subjectType)) {
        logger.error(subjectType, 'not allow');
        return;
    }

    let bgmStorageSetting = {
        'class': MyStorage,
        '__default': {'prefix': 'bgm|df', 'expireDay': null},
        'getSubject': {'prefix': 'bgm|subj', 'expireDay': null},
        'getRelated': {'prefix': 'bgm|rela', 'expireDay': 7},
    }
    let bgmApi = new BangumiApi(bgmStorageSetting);
    let bgmId = window.location.href.split('/').pop();
    let subjectRes, asMovie;
    if (!asTV && document.querySelector('h1 > small.grey')?.textContent == '剧场版') {
        subjectRes = await bgmApi.getSubject(bgmId);
        asMovie = true;

    } else {
        subjectRes = await bgmApi.getFistSeason(bgmId);

    }
    logger.info('bgmSubjectRes', subjectRes);

    if (!subjectRes) {
        return;
    }
    let bgmNamelist = [subjectRes.name, subjectRes.name_cn];
    let bgmType = subjectRes.platform;
    switch (bgmType) {
        case 'TV':
            bgmType = 'Series'
            break;
        case '剧场版':
            bgmType = 'Movie'
            break;
        default:
            bgmType = 'Series,Movie'
            break;
    }
    let bgmDate = subjectRes.date;
    let addedElements = []
    let adder;
    for (const bgmName of bgmNamelist) {
        adder = new EmbyLinkAdder({
            titleSelector: '#headerSubject > h1',
            searchMethod: EmbyApi.prototype.searchByName.name,
            searchArgs: [bgmName, bgmDate, bgmType],
            adderMethod: EmbyLinkAdder.prototype.beforeendTitleAdder.name,
        })
        await adder.mainAdder();
        addedElements = [...addedElements, ...adder.addedElements]
    }

    if (!myBool(addedElements)) {
        if (asMovie) {
            logger.info('search as movie fail, fallback to tv first season');
            bgmSubjectPage(true);
            return;
        }
        adder.notResultTitleAdder('beforeend');
    }
}

async function doubanMoviePage() {
    if (window.location.host != 'movie.douban.com') {
        return
    }

    let imdbA = document.querySelector('#info > a[href*="imdb.com/title"]');
    if (!imdbA) {
        return;
    }
    let imdbId = imdbA.href.split('/').at(-1);

    let titleSelector = '#wrapper > #content > h1';
    let adder = new EmbyLinkAdder({
        titleSelector: titleSelector,
        searchMethod: EmbyApi.prototype.searchByProviiderIds.name,
        searchArgs: [{'imdb': imdbId}],
        adderMethod: EmbyLinkAdder.prototype.titleAdder.name,
    })
    await adder.mainAdder();

    if (!myBool(adder.addedElements)) {
        adder.notResultTitleAdder();
    }
}

async function imdbTitlePage() {
    if (window.location.host != 'www.imdb.com') {
        return
    }

    let imdbId = document.querySelector('meta[property="imdb:pageConst"]')?.getAttribute('content');
    let metaTitle = document.querySelector('meta[property="imdb:pageType"]')?.getAttribute('content');
    let metaMain = document.querySelector('meta[property="imdb:subPageType"]')?.getAttribute('content');
    let allEpsButton = document.querySelector('a.subnav__all-episodes-button');
    if (allEpsButton || !(imdbId && metaTitle === 'title' && metaMain === 'main')) {
        return;
    }

    let idAdder = new ProviderIdsAdder({
        anchorSelector: 'ul.ipc-inline-list[role="presentation"]:not([data-testid])',
        inputId: ['imdb', imdbId],
        targetProviders: ['tmdb'],
        adderMethod: ProviderIdsAdder.prototype.imdbPageAdder.name,
    })

    let titleSelector = 'h1[data-testid="hero__pageTitle"]';
    let emAdder = new EmbyLinkAdder({
        titleSelector: titleSelector,
        searchMethod: EmbyApi.prototype.searchByProviiderIds.name,
        searchArgs: [{'imdb': imdbId}],
        adderMethod: EmbyLinkAdder.prototype.whiteTitleAdder.name,
    })

    await Promise.all([
        idAdder.mainAdder(),
        emAdder.mainAdder(),
    ]);

    if (!myBool(emAdder.addedElements)) {
        emAdder.notResultTitleAdder();
    }

}

async function tmdbTitlePage() {
    if (window.location.host != 'www.themoviedb.org') {
        return
    }

    let titleSelector = '#original_header .title[class*="ott"]';
    let tmdbId = document.querySelector(`${titleSelector} h2 a`)?.getAttribute('href');
    if (!tmdbId) {
        return;
    }

    function extractAndConvert(input) {
        const regex = /\/(tv|movie)\/(\d+)/;
        const match = input.match(regex);
        if (match) {
            const emType = match[1] === 'tv' ? 'Series' : 'Movie';
            const number = match[2];
            return [number, match[1], emType];
        }
        return [null, null, null];
    }

    let tmType, emType;
    [tmdbId, tmType, emType] = extractAndConvert(tmdbId);
    let tmdbIdStr = `${tmType}/${tmdbId}`;

    let idAdder = new ProviderIdsAdder({
        anchorSelector: 'div.title > div.facts > span.genres',
        inputId: ['tmdb', tmdbIdStr],
        targetProviders: ['imdb', 'tvdb', 'douban'],
        adderMethod: ProviderIdsAdder.prototype.linkAdder.name,
    })

    let emAdder = new EmbyLinkAdder({
        titleSelector: titleSelector,
        searchMethod: EmbyApi.prototype.searchByProviiderIds.name,
        searchArgs: [{'tmdb': tmdbId}, emType],
        adderMethod: EmbyLinkAdder.prototype.titleAdder.name,
    })

    await Promise.all([
        idAdder.mainAdder(),
        emAdder.mainAdder(),
    ]);

    if (!myBool(emAdder.addedElements)) {
        emAdder.notResultTitleAdder();
    }
}

async function traktTitlePage() {
    if (window.location.host != 'trakt.tv') {
        return;
    }
    if (window.location.pathname.split('/').filter(Boolean).length > 2) {
        return;
    }
    let imdbId = document.getElementById('external-link-imdb')?.getAttribute('href').split('/').at(-1);
    if (!imdbId) {
        return;
    }

    let titleSelector = '#summary-wrapper h1';
    let adder = new EmbyLinkAdder({
        titleSelector: titleSelector,
        searchMethod: EmbyApi.prototype.searchByProviiderIds.name,
        searchArgs: [{'imdb': imdbId}],
        adderMethod: EmbyLinkAdder.prototype.whiteTitleAdder.name,
    })
    await adder.mainAdder();

    if (!myBool(adder.addedElements)) {
        adder.notResultTitleAdder();
    }
}

async function tvdbTitlePage() {
    if (window.location.host != 'thetvdb.com') {
        return
    }

    let seriesTitle = document.querySelector('#series_title')
    let tvdbId = document.querySelector('#series_basic_info li')?.textContent?.match(/\d+/)?.[0];
    if (![seriesTitle, tvdbId].every(v => v)) {
        return;
    }
    let imdbId = document.querySelector('#series_basic_info a[href*="imdb.com/title"]')?.href.match(/tt\d+/)[0];
    let idsDict = (imdbId) ? {'tvdb': tvdbId, 'imdb': imdbId} : {'tvdb': tvdbId}
    let titleSelector = '#series_title';
    let adder = new EmbyLinkAdder({
        titleSelector: titleSelector,
        searchMethod: EmbyApi.prototype.searchByProviiderIds.name,
        searchArgs: [idsDict],
        adderMethod: EmbyLinkAdder.prototype.titleAdder.name,
    })
    await adder.mainAdder();

    if (!myBool(adder.addedElements)) {
        adder.notResultTitleAdder();
    }
}

async function googleTitlePage() {
    if (window.location.host != 'www.google.com') {
        return;
    }
    let titleSelector = 'div[data-attrid="title"][role="heading"]'
    let titleElement = document.querySelector(titleSelector);
    let yearElement = document.querySelector('div[data-attrid="subtitle"][role="heading"]');
    if (![titleElement, yearElement].every(v => v)) {
        return;
    }
    let videoTitle = titleElement.textContent;
    let videoYear = yearElement.textContent.match(/\d\d\d\d/)[0];
    let _cleanTitle = videoTitle.split('&').at(-1);
    let typeSelector = `div[data-eas][data-fhs][data-maindata*="${_cleanTitle}"]`;
    let typeElement = document.querySelector(typeSelector);
    // let thumbsUpEl = document.querySelector('div[data-attrid*="thumbs_up"]');

    let videoType = typeElement ? JSON.parse(typeElement.getAttribute('data-maindata'))[4][0] : null;
    if (videoType == null) {
        if (yearElement.textContent.includes('season')) {
            videoType = 'TV';
        }
        let tvReviewEl = document.querySelector('div[data-attrid="kc:/tv/tv_program:reviews"]');
        let mvReviewEl = document.querySelector('div[data-attrid="kc:/film/film:reviews"]');
        if (tvReviewEl) {
            videoType = 'TV';
        } else if (mvReviewEl) {
            videoType = 'FILM';
        }

    }
    let allowTypes = ['FILM', 'TV'];
    if (!allowTypes.includes(videoType)) {
        logger.error(videoType, 'not allow');
        return;
    }

    let imdbEl = document.querySelector('#rhs a[href*="imdb.com/title"]');
    let imdbId = imdbEl?.href.match(/tt\d+/)[0];
    let emAdder;
    let addedElements = []
    if (imdbId) {
        let idAdder = new ProviderIdsAdder({
            anchorSelector: '#rhs a[href*="imdb.com/title"]',
            inputId: ['imdb', imdbId],
            targetProviders: ['tmdb', 'douban'],
            adderMethod: ProviderIdsAdder.prototype.googlePageAdder.name,
        })
        emAdder = new EmbyLinkAdder({
            titleSelector: titleSelector,
            searchMethod: EmbyApi.prototype.searchByProviiderIds.name,
            searchArgs: [{'imdb': imdbId}],
            adderMethod: EmbyLinkAdder.prototype.titleFatherAdder.name,
        });
        await Promise.all([
            emAdder.mainAdder(),
            idAdder.mainAdder(),
        ])
        addedElements = [...addedElements, ...emAdder.addedElements]
    } else {
        switch (videoType) {
            case 'TV':
                videoType = 'Series'
                break;
            case 'FILM':
                videoType = 'Movie'
                break;
            default:
                videoType = 'Series,Movie'
                break;
        }
        let titleSplit = videoTitle.split('(');
        let mainTitle = titleSplit[0].trim();
        let subTitle = titleSplit[1] ? titleSplit[1].replace(')', '').trim() : '';
        for (videoTitle of [mainTitle, subTitle].filter(i => i)) {
            emAdder = new EmbyLinkAdder({
                titleSelector: titleSelector,
                searchMethod: EmbyApi.prototype.searchByName.name,
                searchArgs: [videoTitle, `${videoYear}-01-01`, videoType, 1, 365],
                adderMethod: EmbyLinkAdder.prototype.titleFatherAdder.name,
            });
            await emAdder.mainAdder();
            addedElements = [...addedElements, ...emAdder.addedElements]
        }
    }

    if (!myBool(addedElements)) {
        emAdder.notResultTitleAdder();
    }
}

async function embySearchOtherVerVideo() {
    let itemId = /\?id=(\w+)/.exec(window.location.hash);
    if (!itemId) {
        alert('未找到 itemId, 请在 Emby 条目页面中搜索')
        return;
    }
    itemId = itemId[1];
    let oldElements = document.querySelectorAll('[add-by="embyEverywhere"]');
    oldElements.forEach(el => el.remove());
    logger.info(itemId);
    let itemInfo = await ApiClient.getItem(ApiClient._serverInfo.UserId, itemId);
    let proviiderIds = itemInfo.ProviderIds;
    let titleSelector = '[class="itemName-primary"]'
    let adder = new EmbyLinkAdder({
        titleSelector: titleSelector,
        searchMethod: EmbyApi.prototype.searchByProviiderIds.name,
        searchArgs: [proviiderIds, itemInfo.Type],
        adderMethod: EmbyLinkAdder.prototype.whiteTitleAdder.name,
    })
    await adder.mainAdder();

}

async function embyItemPage() {
    GM_registerMenuCommand('Emby: 搜索其他相同条目', embySearchOtherVerVideo);
}

async function main() {
    storageUndefinedClear();
    embyServerDatas = settingsSaverBase('embyServerDatas', embyServerDatas);
    await Promise.all([
        doubanPlayedByTrakt(),
        bgmSubjectPage(),
        doubanMoviePage(),
        imdbTitlePage(),
        tmdbTitlePage(),
        traktTitlePage(),
        tvdbTitlePage(),
        googleTitlePage(),
        embyItemPage(),
    ]);

}

(async () => {
    await main();
})();
