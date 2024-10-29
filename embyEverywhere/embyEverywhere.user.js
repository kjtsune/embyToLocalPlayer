// ==UserScript==
// @name         embyEverywhere
// @description  add Emby search result in many sites。eg: imdb.com trakt.tv tmdb tvdb
// @description:zh-CN   在许多网站上添加 Emby 跳转链接。例如: bgm.tv douban imdb tmdb tvdb trakt
// @namespace    https://github.com/kjtsune/embyToLocalPlayer
// @version      2024.10.06
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
// @grant        GM_xmlhttpRequest
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_deleteValue
// @connect      *
// @license      MIT
// ==/UserScript==

'use strict';

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

// 以下为测试功能，不用管他

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

function stringify(value) {
    if (value !== null && typeof value === 'object') { return JSON.stringify(value) };
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

class MyStorage {
    constructor(prefix, expireDay = 0, splitStr = '|', useGM = false) {
        this.prefix = prefix;
        this.splitStr = splitStr;
        this.expireDay = expireDay;
        this.expireMs = expireDay * 864E5;
        this.useGM = useGM;
        this._getItem = (useGM) ? GM_getValue : localStorage.getItem.bind(localStorage);
        this._setItem = (useGM) ? GM_setValue : localStorage.setItem.bind(localStorage);
        this._removeItem = (useGM) ? GM_deleteValue : localStorage.removeItem.bind(localStorage);
    }

    _dayToMs(day) {
        return day * 864E5;
    }

    _msToDay(ms) {
        return ms / 864E5;
    }

    _keyGenerator(key) {
        return `${this.prefix}${this.splitStr}${key}`
    }

    get(key, defalut = null) {
        key = this._keyGenerator(key);
        let res = this._getItem(key);
        if (this.expireMs && res) {
            let data = (this.useGM) ? res : JSON.parse(res);
            let timestamp = data.timestamp;
            if (timestamp + this.expireMs < Date.now()) {
                res = null;
            } else {
                res = data.value;
            }
        } else if (!this.useGM && res) {
            try {
                res = JSON.parse(res);
            } catch (_error) {
                // pass
            }
        }
        res = res || defalut;
        return res
    }

    set(key, value) {
        key = this._keyGenerator(key);
        if (this.expireMs) {
            value = { timestamp: Date.now(), value: value };
        }
        if (!this.useGM && typeof (value) == 'object') {
            value = JSON.stringify(value)
        }
        this._setItem(key, value)
    }

    del(key) {
        key = this._keyGenerator(key);
        try {
            this._removeItem(key);
        } catch (_error) {
            // pass
        }
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

class BaseApi {
    constructor(host, storageSetting = null) {
        host = new URL(host);
        this.host = `${host.protocol}//${host.host}`;
        this.headers = {};
        this.storage = {};
        if (storageSetting) { this._initStorage(storageSetting); }
        this._trimStringProperties();
    }

    _trimStringProperties() {
        for (const key in this) {
            if (typeof this[key] === 'string') {
                this[key] = this[key].trim();
            }
        }
    }

    _initStorage(storageSetting) {
        // storageSetting = {
        //     'class': MyStorage,
        //     '__default': {'prefix': 'bgm|df', 'expireDay':null},
        //     'getSubject': {'prefix': 'bgm|subj', 'expireDay':null},
        //     'getRelated': {'prefix': 'bgm|rela', 'expireDay':7},
        // }
        let Storage = storageSetting['class'];
        delete storageSetting['class'];
        for (const key in storageSetting) {
            let settings = storageSetting[key];
            this.storage[key] = new Storage(settings.prefix, settings.expireDay)
        }
    }

    _req(method, path, params = null, json = null, preload = null) {
        let query = (params) ? new URLSearchParams(params).toString() : '';
        let url = (query) ? `${this.host}/${path}?${query}` : `${this.host}/${path}`;
        let headers = (myBool(this.headers)) ? this.headers : undefined;
        let data = (json) ? JSON.stringify(json) : undefined;
        if (method === 'POST' && preload) {
            data = new URLSearchParams(preload);
            headers = headers || {}
            headers = { ...headers, ...{ 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', } }
        }
        let res = new Promise((resolve) => {
            let isResolved = false;
            const timeout = setTimeout(() => {
                if (!isResolved) {
                    console.error(`Request to ${url} timed out after 8 seconds.`);
                    resolve();
                    isResolved = true;
                }
            }, 8000);

            GM_xmlhttpRequest({
                method: method,
                url: url,
                headers: headers,
                data: data,
                onload: function (response) {
                    if (!isResolved) {
                        clearTimeout(timeout);
                        if (response.status >= 200 && response.status < 400) {
                            let _res = JSON.parse(response.responseText);
                            resolve(_res);
                            console.info(`xmlhttp getting ${url}:`, response.status, response.statusText, _res);
                        } else if (response.status > 400) {
                            console.error(`Error getting ${url}:`, response.status, response.statusText);
                            resolve();
                        } else {
                            console.error(`Error getting ${url}:`, response.status, response.statusText, response.responseText);
                            resolve();
                        }
                        isResolved = true;
                    }
                },
                onerror: function (response) {
                    if (!isResolved) {
                        clearTimeout(timeout);
                        console.error(`Error during GM_xmlhttpRequest to ${url}:`, response.statusText);
                        resolve();
                        isResolved = true;
                    }
                }
            });
        });

        return res;
    }

    _get(path, params = null) {
        return this._req('GET', path, params);
    }

    _post(path, json = null, params = null) {
        return this._req('POST', path, params, json);
    }

    async _getWithStorage(key, url, funcName) {
        let storageCur = (Object.prototype.hasOwnProperty.call(this.storage, funcName)) ? this.storage[funcName] : null;
        let res = (storageCur) ? storageCur.get(key) : null;
        if (res) {
            res = (typeof (res) == 'object') ? res : JSON.parse(res);
        } else {
            res = await this._get(url);
            storageCur && res && storageCur.set(key, res);
        }
        return res;
    }

}

class BangumiApi extends BaseApi {
    constructor(storageSetting = null, userName = null, accessToken = null, isPrivate = true) {
        super('https://api.bgm.tv/v0', storageSetting); // v0 会被清除。
        this.userName = userName;
        this.accessToken = accessToken;
        this.isPrivate = isPrivate;
        this._trimStringProperties();
    }
    async _get(path, params = null) {
        let res = await this._req('GET', `v0/${path}`, params);
        if (res !== null && typeof res === 'object' && res.error == 'Not Found') { return null; }
        return res;
    }

    async getSubject(subjectId) {
        let key = subjectId;
        let url = `subjects/${subjectId}`;
        let funcName = this.getSubject.name;
        let res = await this._getWithStorage(key, url, funcName);
        return res;
    }

    async getRelated(subjectId) {
        let key = subjectId;
        let url = `subjects/${subjectId}/subjects`;
        let funcName = this.getRelated.name;
        let res = await this._getWithStorage(key, url, funcName);
        return res;
    }

    async getFistSeason(subjectId) {
        let curId = subjectId;
        while (true) {
            let curRelated = await this.getRelated(curId)
            logger.info('curRelated', curRelated);
            let preSubj = (curRelated.error != 'Not Found') ? curRelated.filter(i => i.relation === '前传') : null;
            if (myBool(preSubj)) {
                curId = preSubj[0]['id'];
                continue
            } else {
                return this.getSubject(curId);
            }
        }

    }
}

class EmbyApi extends BaseApi {
    constructor(host, apiKey = '', userId = '', userName = '', passWord = '') {
        super(host);
        this.apiKey = apiKey;
        this.userId = userId;
        this.userName = userName;
        this.passWord = passWord;
        this._defaultFields = [
            'PremiereDate',
            'ProviderIds',
            'CommunityRating',
            'CriticRating',
            'OriginalTitle',
            'Path',
        ].join(',');
        this._trimStringProperties();
        this._updateParamsGet();
    }

    _updateParamsGet() {
        this._paramsGet = { 'api_key': this.apiKey };
    }

    _get(path, params = null) {
        path = `emby/${path}`;
        return super._get(path, { ...this._paramsGet, ...params });
    }

    async checkTokenAlive() {
        if ([this.apiKey, this.userName, this.passWord].every(v => !v)) { throw ('emby apikey or password require'); }
        let apiDb = new MyStorage('emby|api', undefined, undefined, true);
        let apiWorkDb = new MyStorage('emby|apiWork', 1, undefined, true);
        let host = new URL(this.host).host;
        this.apiKey = this.apiKey || apiDb.get(host);
        this._updateParamsGet();
        // 仅每天检查一次。
        let workDbKey = `${host}|${this.apiKey}`
        if (apiWorkDb.get(workDbKey)) { return; }
        let isWork;
        if (this.apiKey) {
            isWork = await this._get('System/Info');
            logger.info(`Emby checkTokenAlive by ${host}`)
        } else {
            isWork = false;
        }
        if (isWork) {
            apiWorkDb.set(workDbKey, true);
            return;
        }
        // 仅设置 apiKey，apiKey 最优先。
        if (this.apiKey && !apiDb.get(host)) {
            throw new Error(`Emby api auth fail, ${this.host}  ${this.apiKey}`);
        }
        let authData;
        // 首次运行时，或者储存的密钥失效。
        if (!this.apiKey && !apiDb.get(host) || apiDb.get(host)) {
            authData = await this.authByName();
            this.apiKey = authData.AccessToken;
            this.apiKey && apiDb.set(host, this.apiKey);
            this._updateParamsGet();
            logger.info(`Emby authByName by ${host}`)
            return;
        }
        throw new Error(`Emby auth fail, ${this.host}  ${this.userName}  ${this.passWord}`);
    }

    async authByName() {
        let headers = this.headers;
        let res = await this._req('POST', 'emby/Users/authenticatebyname', {
            'X-Emby-Client': 'Emby Web',
            'X-Emby-Device-Id': 'Chrome Windows',
            'X-Emby-Client-Version': '4.8.8.0'
        },
            null,
            { 'Username': this.userName, 'Pw': this.passWord })
        this.headers = headers
        return res
    }

    async getGenreId(genre) {
        let res = await this._get(`Genres/${genre}`).Id
        if (!res) { throw `Genres/${genre} not exists, check it`; }
        return res;
    }

    async getItems({ genre = '', types = 'Movie,Series,Video', fields = null, startIndex = 0,
        ids = null, limit = 50, parentId = null,
        sortBy = 'DateCreated,SortName', recursive = true, extParams = null }) {
        fields = fields || this._defaultFields;
        let params = {
            'HasTmdbId': true,
            'SortBy': sortBy,
            'SortOrder': 'Descending',
            'IncludeItemTypes': types,
            'Recursive': recursive,
            'Fields': fields,
            'StartIndex': startIndex,
            'Limit': limit,
            'api_key': this.apiKey,
        };
        if (genre) {
            params['GenreIds'] = await this.getGenreId(genre);
        }
        if (ids) {
            params['Ids'] = ids;
        }
        if (parentId) {
            params['ParentId'] = parentId;
        }
        if (extParams) {
            Object.assign(params, extParams);
        }

        return await this._get('Items', params);
    }

    async searchByName(name, premiereDate = null, itemTypes = 'Series,Movie', daysBefore = 10, daysAfter = 20) {
        let query = {
            'Fields': this._defaultFields,
            'Recursive': true,
            'GroupProgramsBySeries': true,
            'SearchTerm': name,
        }
        if (premiereDate) {
            premiereDate = new Date(premiereDate);
            premiereDate.setDate(premiereDate.getDate() - daysBefore);
            let minDate = premiereDate.toISOString().slice(0, 10);
            premiereDate.setDate(premiereDate.getDate() + daysAfter);
            let maxDate = premiereDate.toISOString().slice(0, 10);
            query['MinPremiereDate'] = minDate;
            query['MaxPremiereDate'] = maxDate;
        }
        if (itemTypes) {
            query['IncludeItemTypes'] = itemTypes;
        }
        let userPath = '';
        if (this.userId) {
            userPath = `Users/${this.userId}/` // 加用户ID会将不同路径的相同条目合并为一个。但会慢一点。
        }
        let res = await this._get(`${userPath}Items`, query);
        return res.Items;
    }

    async searchByProviiderIds(tkIds, type = undefined) {
        // 只能搜索主条目，集和季不行
        const idsParam = Object.entries(tkIds)
            .filter(([k, v]) => v && (type || k !== 'tmdb')) // 修改这一行
            .map(([k, v]) => `${k}.${v}`)
            .join(',');

        const extParams = { AnyProviderIdEquals: idsParam };
        const res = await this.getItems({ extParams: extParams, types: type });
        return res.Items;
    }

    itemObjToUrl(item) {
        let url = `${this.host}/web/index.html#!/item?id=${item.Id}&serverId=${item.ServerId}`
        return url;
    }
}

class TraktApi extends BaseApi {
    constructor(userName, clientId, clientSecret, tokenObj) {
        super('https://api.trakt.tv');
        this.userName = userName;
        this.clientId = clientId;
        this.clientSecret = clientSecret;
        this.tokenObj = tokenObj;
        this.headers = {
            'Accept': 'application/json',
            'trakt-api-key': this.clientId,
            'trakt-api-version': '2',
        };
        if (![this.userName, this.clientId, this.clientSecret, myBool(this.tokenObj)].every(v => v)) {
            throw new Error('Require userName, clientId, clientSecret, tokenObj.');
        }
        this._updateHeader()
    }

    _updateHeader() {
        this.headers['Authorization'] = `Bearer ${this.tokenObj.access_token}`;
    }

    async refreshToken() {
        let expiresTime = this.tokenObj.created_at + this.tokenObj.expires_in;
        if (expiresTime > Date.now() / 1000 + 15 * 86400) {
            this.headers['Authorization'] = `Bearer ${this.tokenObj.access_token}`;
            return;
        } else {
            let data = {
                'refresh_token': this.tokenObj['refresh_token'],
                'client_id': this.clientId,
                'client_secret': this.clientSecret,
                'redirect_uri': 'http://localhost:58000/trakt',
                'grant_type': 'refresh_token'
            };

            let tokenObj = await this._req('POST', 'oauth/token', data);

            if (!myBool(tokenObj)) {
                logger.info('trakt: refreshToken error', tokenObj);
                return;
            }
            this.tokenObj = tokenObj;
            this._updateHeader();
            logger.info('trakt: refreshToken success', tokenObj);
            return tokenObj;
        }
    }

    async _test() {
        let res = await this._get('calendars/my/dvd/2000-01-01/1')
        logger.info('trakt test', res)
    }

    async idLookup(provider, id, type = '') {
        if (type) {
            type = provider === 'imdb' ? '' : `?type=${type}`;
        }
        const allowedProviders = ['tvdb', 'tmdb', 'imdb', 'trakt'];
        if (!allowedProviders.includes(provider)) {
            throw new Error(`id_type allow: ${allowedProviders}`);
        }
        const res = await this._get(`search/${provider}/${id}${type}`);
        return res;
    }

    async getWatchHistory(idsItem) {
        const type = idsItem.type;
        let pathType = type ? `${type}s` : '';
        pathType = pathType || 'episodes';
        const traktId = type ? idsItem[type].ids.trakt : idsItem.trakt;
        const res = await this._get(`users/${this.userName}/history/${pathType}/${traktId}`);
        return res;
    }

    async getShowWatchedProgress(id) {
        // Trakt ID, Trakt slug, or IMDB ID
        // 含有 aired 的数据，重置的 api 需要 vip
        const res = this._get(`shows/${id}/progress/watched`);
        return res;
    }

    async checkIsWatched(idsItem, returnList = null) {
        // id_lookup -> ids_item
        // returnList -> [bool, watchedData]
        let type = idsItem.type;
        let res;

        if (type === 'movie') {
            res = await this.getWatchHistory(idsItem);
            if (myBool(res)) {
                return (returnList) ? [myBool(res), res[0]] : res[0];

            }
            return (returnList) ? [myBool(res), {}] : {};
        }

        if (type === 'episode') {
            let show = await this.getShowWatchedProgress(idsItem['show'].ids.trakt);
            let seaNum = idsItem.episode.season;
            res = show.seasons.find(season => season.number === seaNum);

        } else {
            const traktId = type ? idsItem[type].ids.trakt : idsItem.trakt;
            res = await this.getShowWatchedProgress(traktId);
        }

        const aired = res.aired;
        const completed = res.completed;

        if (completed >= aired) {
            return (returnList) ? [true, res] : res;
        }
        return (returnList) ? [false, res] : false;
    }

}

async function doubanPlayedByTrakt() {
    if (window.location.host != 'movie.douban.com') { return; }

    traktSettings = settingsSaverBase('traktSettings', traktSettings, true);
    traktSettings = (typeof (traktSettings) == 'string') ? JSON.parse(traktSettings) : traktSettings;

    if (!traktSettings) { return; }
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

    let imdbA = document.querySelector('#info > a[href*="imdb.com/title"]');
    if (!imdbA) { return; }
    let imdbId = imdbA.href.split('/').at(-1);

    let imdbWatchedDb = new MyStorage('imdb|watched', 7)
    let imdbWatched = imdbWatchedDb.get(imdbId);
    let watchedState, watchedData, tkIds;
    if (imdbWatched) {
        [watchedState, watchedData] = [true, {}]
    } else {
        tkIds = await traktApi.idLookup('imdb', imdbId);
        tkIds = tkIds[0]
        if (!myBool(tkIds)) {
            logger.error('traktApi.idLookup not result, skip mark played');
            return;
        }
        let tmdbType = (tkIds.type == 'movie') ? 'movie' : 'tv';
        let tmdbId = tkIds[tkIds.type].ids.tmdb;
        let tmdbHtml = `<a id="tmdbLink" href="https://www.themoviedb.org/${tmdbType}/${tmdbId}" target="_blank">  tmdb</a>`
        if (tmdbId) {
            imdbA.insertAdjacentHTML('afterend', tmdbHtml);
        }
        logger.info(`trakt ${stringify(tkIds)}`);
        [watchedState, watchedData] = await traktApi.checkIsWatched(tkIds, true);
        if (watchedState) { imdbWatchedDb.set(imdbId, true); }
    }
    logger.info(`trakt watchedState ${stringify(watchedState)}`);
    let watchedEmoji = (watchedState) ? '✔️' : '✖️';
    let watchedStr = ''
    if (!watchedState && watchedData.aired) {
        watchedStr = ` ${((watchedData.completed / watchedData.aired) * 100).toFixed(0)}%`
    }
    imdbA.previousElementSibling.insertAdjacentHTML('beforebegin', `<span class="pl">看过:</span>${watchedStr} ${watchedEmoji}<br>`);
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
        if (document.querySelector('img[add-by="embyEverywhere"]')) { return; }
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
        if (this.searchMethod == 'searchByName' && (!this.searchArgs[0])) { return; }
        for (const embyServer of embyServerDatas) {
            if (document.getElementById(embyServer.name)) { continue; }
            let embyApi = new EmbyApi(embyServer.url, embyServer.apiKey, embyServer.userId, embyServer.userName, embyServer.passWord);
            searchPromises.push(
                (async () => {
                    let searchData;
                    try {
                        await embyApi.checkTokenAlive();
                        searchData = await embyApi[this.searchMethod](...this.searchArgs);
                    } catch (_error) {
                        let resData = { 'name': embyServer.name, 'url': false };
                        this[this.adderMethod](resData);
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
                            let resData = { 'name': embyServer.name, 'url': itemUrl };
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

    titleAdder(data, extHtml = '', position = 'beforebegin') { // beforeend
        let title = document.querySelector(this.titleSelector);
        let elementId = `${data.name}`
        let linkHtml = `<a id=${elementId} target="_blank" add-by="embyEverywhere"`
        let embyLink = `${linkHtml} href="${data.url}"${extHtml}>${data.name},</a>`;
        if (!data.url) {
            embyLink = `${linkHtml}${extHtml}>${data.name}🚧,</a>`;
        }
        title.insertAdjacentHTML(position, embyLink);
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
    if (!bgmAllowDomains.includes(curDomain)) { return; }
    let allowTypes = ['v:Movie',]
    let headerSubject = document.getElementById('headerSubject');
    let subjectType = (headerSubject) ? headerSubject.getAttribute('typeof') : 'not bgm page';
    if (!allowTypes.includes(subjectType)) {
        logger.error(subjectType, 'not allow');
        return;
    };

    let bgmStorageSetting = {
        'class': MyStorage,
        '__default': { 'prefix': 'bgm|df', 'expireDay': null },
        'getSubject': { 'prefix': 'bgm|subj', 'expireDay': null },
        'getRelated': { 'prefix': 'bgm|rela', 'expireDay': 7 },
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

    if (!subjectRes) { return; }
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
    if (window.location.host != 'movie.douban.com') { return };
    let imdbA = document.querySelector('#info > a[href*="imdb.com/title"]');
    if (!imdbA) { return; }
    let imdbId = imdbA.href.split('/').at(-1);

    let titleSelector = '#wrapper > #content > h1';
    let adder = new EmbyLinkAdder({
        titleSelector: titleSelector,
        searchMethod: EmbyApi.prototype.searchByProviiderIds.name,
        searchArgs: [{ 'imdb': imdbId }],
        adderMethod: EmbyLinkAdder.prototype.titleAdder.name,
    })
    await adder.mainAdder();

    if (!myBool(adder.addedElements)) {
        adder.notResultTitleAdder();
    }
}

async function imdbTitlePage() {
    if (window.location.host != 'www.imdb.com') { return };
    let imdbId = document.querySelector('meta[property="imdb:pageConst"]')?.getAttribute('content');
    let metaTitle = document.querySelector('meta[property="imdb:pageType"]')?.getAttribute('content');
    let metaMain = document.querySelector('meta[property="imdb:subPageType"]')?.getAttribute('content');
    let allEpsButton = document.querySelector('a.subnav__all-episodes-button');
    if (allEpsButton || !(imdbId && metaTitle === 'title' && metaMain === 'main')) { return; }

    let titleSelector = 'h1[data-testid="hero__pageTitle"]';
    let adder = new EmbyLinkAdder({
        titleSelector: titleSelector,
        searchMethod: EmbyApi.prototype.searchByProviiderIds.name,
        searchArgs: [{ 'imdb': imdbId }],
        adderMethod: EmbyLinkAdder.prototype.whiteTitleAdder.name,
    })
    await adder.mainAdder();

    if (!myBool(adder.addedElements)) {
        adder.notResultTitleAdder();
    }
}

async function tmdbTitlePage() {
    if (window.location.host != 'www.themoviedb.org') { return };
    let titleSelector = '#original_header .title[class*="ott"]';
    let tmdbId = document.querySelector(`${titleSelector} h2 a`)?.getAttribute('href');
    if (!tmdbId) { return; }

    function extractAndConvert(input) {
        const regex = /\/(tv|movie)\/(\d+)/;
        const match = input.match(regex);
        if (match) {
            const typeMedia = match[1] === 'tv' ? 'Series' : 'Movie';
            const number = match[2];
            return [number, typeMedia];
        }
        return [null, null];
    }

    let type;
    [tmdbId, type] = extractAndConvert(tmdbId);

    let adder = new EmbyLinkAdder({
        titleSelector: titleSelector,
        searchMethod: EmbyApi.prototype.searchByProviiderIds.name,
        searchArgs: [{ 'tmdb': tmdbId }, type],
        adderMethod: EmbyLinkAdder.prototype.titleAdder.name,
    })
    await adder.mainAdder();

    if (!myBool(adder.addedElements)) {
        adder.notResultTitleAdder();
    }
}

async function traktTitlePage() {
    if (window.location.host != 'trakt.tv') { return };
    let imdbId = document.getElementById('external-link-imdb')?.getAttribute('href').split('/').at(-1);;
    if (!imdbId) { return; }

    let titleSelector = '#summary-wrapper h1';
    let adder = new EmbyLinkAdder({
        titleSelector: titleSelector,
        searchMethod: EmbyApi.prototype.searchByProviiderIds.name,
        searchArgs: [{ 'imdb': imdbId }],
        adderMethod: EmbyLinkAdder.prototype.whiteTitleAdder.name,
    })
    await adder.mainAdder();

    if (!myBool(adder.addedElements)) {
        adder.notResultTitleAdder();
    }
}

async function tvdbTitlePage() {
    if (window.location.host != 'thetvdb.com') { return };
    let seriesTitle = document.querySelector('#series_title')
    let tvdbId = document.querySelector('#series_basic_info li')?.textContent?.match(/\d+/)?.[0];
    if (![seriesTitle, tvdbId].every(v => v)) { return; }
    let imdbId = document.querySelector('#series_basic_info a[href*="imdb.com/title"]')?.href.match(/tt\d+/)[0];
    let idsDict = (imdbId) ? { 'tvdb': tvdbId, 'imdb': imdbId } : { 'tvdb': tvdbId }
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
    if (window.location.host != 'www.google.com') { return; }
    let titleElement = document.querySelector('div[data-attrid="title"][role="heading"]');
    let yearElement = document.querySelector('div[data-attrid="subtitle"][role="heading"]');
    if (![titleElement, yearElement].every(v => v)) { return; }
    let videoTitle = titleElement.textContent;
    let videoYear = yearElement.textContent.match(/\d\d\d\d/)[0];
    let _cleanTitle = videoTitle.split('&').at(-1);
    let typeSelector = `div[data-eas][data-fhs][data-maindata*="${_cleanTitle}"]`;
    let typeElement = document.querySelector(typeSelector);
    let videoType = JSON.parse(typeElement.getAttribute('data-maindata'))[4][0];
    let allowTypes = ['FILM', 'TV'];
    if (!allowTypes.includes(videoType)) {
        logger.error(videoType, 'not allow');
        return;
    };
    let imdbId = document.querySelector('#rhs a[href*="imdb.com/title"]')?.href.match(/tt\d+/)[0];
    let adder;
    let addedElements = []
    if (imdbId) {
        adder = new EmbyLinkAdder({
            titleSelector: typeSelector,
            searchMethod: EmbyApi.prototype.searchByProviiderIds.name,
            searchArgs: [{ 'imdb': imdbId }],
            adderMethod: EmbyLinkAdder.prototype.titleAdder.name,
        });
        await adder.mainAdder();
        addedElements = [...addedElements, ...adder.addedElements]
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
            adder = new EmbyLinkAdder({
                titleSelector: typeSelector,
                searchMethod: EmbyApi.prototype.searchByName.name,
                searchArgs: [videoTitle, `${videoYear}-01-01`, videoType, 1, 365],
                adderMethod: EmbyLinkAdder.prototype.titleAdder.name,
            });
            await adder.mainAdder();
            addedElements = [...addedElements, ...adder.addedElements]
        }
    }

    if (!myBool(addedElements)) {
        adder.notResultTitleAdder();
    }
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
    ]);

}

(async () => {
    await main();
})();
