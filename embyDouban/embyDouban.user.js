// ==UserScript==
// @name         embyDouban
// @name:zh-CN   embyDouban
// @name:en      embyDouban
// @namespace    https://github.com/kjtsune/embyToLocalPlayer/tree/main/embyDouban
// @version      2025.09.17
// @description  emby 里展示: 豆瓣 Bangumi bgm.tv 评分 链接 (豆瓣评论可关)
// @description:zh-CN emby 里展示: 豆瓣 Bangumi bgm.tv 评分 链接 (豆瓣评论可关)
// @description:en  show douban Bangumi ratings in emby
// @author       Kjtsune
// @match        *://*/web/index.html*
// @match        *://*/*/web/index.html*
// @match        https://app.emby.media/*
// @icon         https://www.google.com/s2/favicons?sz=64&domain=emby.media
// @grant        GM.xmlHttpRequest
// @grant        GM_registerMenuCommand
// @grant        GM_unregisterMenuCommand
// @connect      api.bgm.tv
// @connect      api.douban.com
// @connect      movie.douban.com
// @connect      query.wikidata.org
// @require      https://fastly.jsdelivr.net/gh/kjtsune/UserScripts@a4c9aeba777fdf8ca50e955571e054dca6d1af49/lib/basic-tool.js
// @require      https://fastly.jsdelivr.net/gh/kjtsune/UserScripts@a4c9aeba777fdf8ca50e955571e054dca6d1af49/lib/my-storage.js
// @license MIT
// ==/UserScript==
'use strict';
/*global ApiClient*/

/// <reference path="./lib/basic-tool.js" />
/*global MyLogger */ // myBool

/// <reference path="./lib/my-storage.js" />
/*global MyStorage*/

let config = {
    logLevel: 2,
    // 清除无效标签的正则匹配规则
    tagsRegex: /\d{4}|TV|动画|小说|漫|轻改|游戏改|原创|[a-zA-Z]/,
    // 标签数量限制，填0禁用标签功能。
    tagsNum: 5,
};

let logger = new MyLogger(config)

let enableDoubanComment = (localStorage.getItem('enableDoubanComment') === 'false') ? false : true;

async function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function switchLocalStorage(key, defaultValue = 'false', trueValue = 'true', falseValue = 'false') {
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

function isHidden(el) {
    return (el.offsetParent === null);
}

function isEmpty(s) {
    return !s || s === 'N/A' || s === 'undefined';
}

function getVisibleElement(elList) {
    if (!elList) { return; }
    if (NodeList.prototype.isPrototypeOf(elList)) {
        for (let i = 0; i < elList.length; i++) {
            if (!isHidden(elList[i])) {
                return elList[i];
            }
        }
    } else {
        console.log('%c%s', 'color: orange;', 'return raw ', elList);
        return elList;
    }

}

function getURL_GM(url, data = null, headers = {}) {
    let method = (data) ? 'POST' : 'GET'
    return new Promise(resolve => GM.xmlHttpRequest({
        method: method,
        url: url,
        data: data,
        headers: headers,
        onload: function (response) {
            if (response.status >= 200 && response.status < 400) {
                resolve(response.responseText);
            } else {
                console.error(`Error ${method} ${url}:`, response.status, response.statusText, response.responseText);
                resolve();
            }
        },
        onerror: function (response) {
            console.error(`Error during GM.xmlHttpRequest to ${url}:`, response.statusText);
            resolve();
        }
    }));
}

async function getJSON_GM(url, data = null, headers = {}) {
    const res = await getURL_GM(url, data, headers);
    if (res) {
        return JSON.parse(res);
    }
}

function textSimilarity(text1, text2) {
    const len1 = text1.length;
    const len2 = text2.length;
    let count = 0;
    for (let i = 0; i < len1; i++) {
        if (text2.indexOf(text1[i]) != -1) {
            count++;
        }
    }
    const similarity = count / Math.min(len1, len2);
    return similarity;
}

function getEmbyTitle() {
    let container = getVisibleElement(document.querySelectorAll('.itemPrimaryNameContainer'));
    if (!container) return '';
    let textTitle = container.querySelector('.itemName-primary');
    if (textTitle && textTitle.textContent) {
        return textTitle.textContent.trim();
    }
    let imgTitle = container.querySelector('.itemName-primary-logo img');
    if (imgTitle) {
        return imgTitle.getAttribute('alt')?.trim() || '';
    }
    return '';
}

async function getDoubanAPI(query) {
    return await getJSON_GM(`https://api.douban.com/v2/${query}`, 'apikey=0ab215a8b1977939201640fa14c66bab',
        { 'Content-Type': 'application/x-www-form-urlencoded; charset=utf8', });
}

async function getDoubanId(imdbId, searchTitle = null) {

    const data = await getDoubanAPI(`movie/imdb/${imdbId}`);
    if (!isEmpty(data?.alt)) {
        return data.alt.split('/').pop();
    }

    const wikidataUrl = 'https://query.wikidata.org/sparql?format=json&query=' +
        encodeURIComponent(`SELECT * WHERE { ?s wdt:P345 "${imdbId}". OPTIONAL { ?s wdt:P4529 ?Douban_film_ID. } }`);
    const wikidataRes = await getJSON_GM(wikidataUrl);
    if (wikidataRes && wikidataRes.results.bindings.length) {
        const item = wikidataRes.results.bindings[0];
        if (item.Douban_film_ID) {
            return item.Douban_film_ID.value;
        }
    }

    if (searchTitle) {
        const search = await getJSON_GM(`https://movie.douban.com/j/subject_suggest?q=${searchTitle}`);
        if (search && search.length > 0 && search[0].id) {
            let doubanId = search[0].id;
            let doubanTitle = search[0].title;
            let doubanSubTitle = search[0].sub_title;
            if (textSimilarity(searchTitle, doubanTitle) < 0.4 && textSimilarity(searchTitle, doubanSubTitle) < 0.4) {
                logger.info(`douban title not match emby:${searchTitle} douban:${doubanTitle} ${doubanSubTitle}`);
                return;
            }
            return doubanId;
        }
    }

    // const suggestUrl = `https://movie.douban.com/j/subject_suggest?q=${imdbId}`;
    // const suggestRes = await getJSON_GM(suggestUrl);
    // if (suggestRes && suggestRes.length) {
    //     return suggestRes[0].id;
    // }

    return null;
}

async function getDoubanInfo(imdbId) {
    if (!imdbId) {
        return;
    }
    let embyTitle = getEmbyTitle();
    let doubanId = await getDoubanId(imdbId, embyTitle)
    if (doubanId) {
        const abstract = await getJSON_GM(`https://movie.douban.com/j/subject_abstract?subject_id=${doubanId}`);
        const average = abstract?.subject?.rate || '?';
        const comment = abstract?.subject?.short_comment?.content;
        return {
            id: doubanId,
            comment: comment,
            // url: `https://movie.douban.com/subject/${doubanId}/`,
            rating: average,
            title: abstract?.subject?.title,
        };
    }
}

function insertDoubanComment(doubanId, doubanComment) {
    console.log('%c%o%s', 'color:orange;', 'start add comment ', doubanId)
    if (!enableDoubanComment) { return; }
    let el = getVisibleElement(document.querySelectorAll('div#doubanComment'));
    if (el || isEmpty(doubanComment)) {
        console.log('%c%s', 'color: orange', 'skip add doubanComment', el, doubanComment);
        return;
    }
    let embyComment = getVisibleElement(document.querySelectorAll('div.overview-text'));
    if (embyComment) {
        let parentNode = (ApiClient._serverVersion.startsWith('4.6')
        ) ? embyComment.parentNode : embyComment.parentNode.parentNode
        parentNode.insertAdjacentHTML('afterend', `<div id="doubanComment"><li>douban comment
        </li>${doubanComment}</li></div>`);
        console.log('%c%s', 'color: orange;', 'insert doubanComment ', doubanId, doubanComment);
    }
}

function insertDoubanScore(doubanId, rating, socreIconHrefClass) {
    console.log('%c%s', 'color: orange;', 'start ', doubanId, rating);
    let el = getVisibleElement(document.querySelectorAll('a#doubanScore'));
    if (el || !rating) {
        console.log('%c%s', 'color: orange', 'skip add score', el, rating);
        return;
    }
    let yearDiv = getVisibleElement(document.querySelectorAll('div[class="mediaInfoItem"]'));
    if (yearDiv) {
        let doubanIco = '<img style="width:16px;" src="data:image/x-icon;base64,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AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP+RwIn////////////4+/j/GnwK/xF3AP8RdwD/EXcA/xF3AP8afAr/+Pv4////////////kcCJ/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/9Xn0v///////////77auf8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP++2rn////////////V59L/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8rhhz/////////////////erNw/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/3qzcP////////////////8rhhz/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/26sZP////////////////81jCf/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/NYwn/////////////////26sZP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/vdm4////////////5PDi/y+IIP8viCD/L4gg/y+IIP8viCD/L4gg/y+IIP8viCD/5PDi////////////vdm4/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/0+bQ/////////////////////////////////////////////////////////////////////////////////////////////////9Pm0P8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP/T5tD/////////////////////////////////////////////////////////////////////////////////////////////////0+bQ/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/9Pm0P///////////9vq2P+Iu4D/iLuA/4i7gP+Iu4D/iLuA/4i7gP+Iu4D/iLuA/4i7gP+Iu4D/iLuA/4i7gP/b6tj////////////T5tD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/0+bQ////////////tdWw/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/7XVsP///////////9Pm0P8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP/T5tD///////////+11bD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/tdWw////////////0+bQ/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/9Pm0P///////////7XVsP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP+11bD////////////T5tD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/0+bQ////////////tdWw/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/7XVsP///////////9Pm0P8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP/T5tD////////////b6tj/iLuA/4i7gP+Iu4D/iLuA/4i7gP+Iu4D/iLuA/4i7gP+Iu4D/iLuA/4i7gP+Iu4D/2+rY////////////0+bQ/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/9Pm0P/////////////////////////////////////////////////////////////////////////////////////////////////T5tD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/0+bQ/////////////////////////////////////////////////////////////////////////////////////////////////9Pm0P8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/+Lu4P//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////4u7g/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/4u7g///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////i7uD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP/i7uD//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////+Lu4P8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AOYRdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwDmEXcASRF3AOYRdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA5hF3AEkAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA==">'
        yearDiv.insertAdjacentHTML('beforebegin', `<div class="starRatingContainer mediaInfoItem douban">${doubanIco}<a id="doubanScore" 
            href="https://movie.douban.com/subject/${doubanId}/" ${socreIconHrefClass}>${rating}</a></div>`);
        console.log('%c%s', 'color: orange;', 'insert score ', doubanId, rating);
    }
    console.log('%c%s', 'color: orange;', 'finish ', doubanId, rating);
}

function imdbIconLinkAdder(imdbHref, socreIconHrefClass) {
    let imdbDiv = getVisibleElement(document.querySelectorAll('div[class="starRatingContainer mediaInfoItem"]'));
    if (isEmpty(imdbDiv)) { return; }
    if (imdbDiv.querySelector('#imdbScoreLink')) { return; }
    let imdbScore = imdbDiv.textContent.match(/[0-9.]+/);
    imdbDiv.lastChild.remove();
    imdbDiv.insertAdjacentHTML('beforeend', `<a id="imdbScoreLink" 
            href="${imdbHref}" ${socreIconHrefClass}>${imdbScore}</a>`)
}

async function insertDoubanMain(linkZone) {
    if (isEmpty(linkZone)) { return; }
    let doubanButton = linkZone.querySelector('a[href*="douban.com"]');
    let imdbButton = linkZone.querySelector('a[href^="https://www.imdb"]');
    if (doubanButton || !imdbButton) { return; }
    let imdbId = imdbButton.href.match(/tt\d+/);
    if (!imdbId) {
        return;
    }
    let socreIconHrefClass = 'class="button-link button-link-color-inherit emby-button" style="font-weight:inherit;" target="_blank"';
    imdbIconLinkAdder(imdbButton.href, socreIconHrefClass);

    let imdbDoubanDb = new MyStorage('imdb|douban');
    let doubanDb = new MyStorage('douban');

    let doubanId = imdbDoubanDb.get(imdbId);

    if (doubanId == '_') { return; }

    let data = doubanDb.get(doubanId);
    if (!isEmpty(data) && data?.rating?.max) {
        data = null; // 去除旧版数据
    }
    if (isEmpty(data)) {
        data = await getDoubanInfo(imdbId);
        console.log('%c%o%s', 'background:yellow;', data, ' result and send a requests')
        if (isEmpty(data)) {
            imdbDoubanDb.set(imdbId, '_');
            return;
        }
        doubanId = data.id;
        imdbDoubanDb.set(imdbId, doubanId);
        doubanDb.set(doubanId, data);
    }
    if (!isEmpty(data)) {
        insertDoubanScore(doubanId, data.rating, socreIconHrefClass);
        if (enableDoubanComment) {
            insertDoubanComment(doubanId, data.comment);
        }

        let buttonClass = imdbButton.className;
        let doubanString = `<a is="emby-linkbutton" class="${buttonClass}" 
    href="https://movie.douban.com/subject/${doubanId}/" target="_blank">
    <i class="md-icon button-icon button-icon-left">link</i>Douban</a>`;
        imdbButton.insertAdjacentHTML('beforebegin', doubanString);
    }
    console.log('%c%o%s', 'color:orange;', 'douban id ', doubanId, String(imdbId));
    if (!imdbDoubanDb.get(imdbId)) {
        imdbDoubanDb.set(imdbId, '_');
        return;
    }

}

function insertBangumiByPath(idNode) {
    let el = getVisibleElement(document.querySelectorAll('a#bangumibutton'));
    if (el) { return; }
    let id = idNode.textContent.match(/(?<=bgm\=)\d+/);
    let bgmHtml = `<a id="bangumibutton" is="emby-linkbutton" class="raised item-tag-button nobackdropfilter emby-button" href="https://bgm.tv/subject/${id}" target="_blank"><i class="md-icon button-icon button-icon-left">link</i>Bangumi</a>`
    idNode.insertAdjacentHTML('beforebegin', bgmHtml);
}

function insertBangumiScore(bgmObj, infoTable, linkZone) {
    if (!bgmObj) return;
    let bgmRate = infoTable.querySelector('a#bgmScore');
    if (bgmRate) return;

    let yearDiv = infoTable.querySelector('div[class="mediaInfoItem"]');
    let bgmHref = `https://bgm.tv/subject/${bgmObj.id}`;
    if (yearDiv && bgmObj.trust) {
        let socreIconHrefClass = 'class="button-link button-link-color-inherit emby-button" style="font-weight:inherit;" target="_blank"';
        let bgmIco = '<img style="width:16px;" src="data:image/x-icon;base64,AAABAAEAEBAAAAEAIABoBAAAFgAAACgAAAAQAAAAIAAAAAEAIAAAAAAAQAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAALJu+f//////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAsm75ELJu+cCybvn/sm75/7Ju+f+ybvn//////7Ju+f+ybvn/sm75/7Ju+f+ybvn/sm75/7Ju+f+ybvnAsm75ELJu+cCybvn/sm75/7Ju+f+ybvn/sm75////////////sm75/7Ju+f+ybvn/sm75/7Ju+f+ybvn/sm75/7Ju+cCwaPn/sGj5/9iz/P///////////////////////////////////////////////////////////9iz/P+waPn/rF/6/6xf+v//////////////////////////////////////////////////////////////////////rF/6/6lW+/+pVvv/////////////////////////////////zXn2/////////////////////////////////6lW+/+lTfz/pU38///////Nefb/zXn2/8159v//////zXn2///////Nefb//////8159v/Nefb/zXn2//////+lTfz/okT8/6JE/P//////////////////////2bb8/8159v/Nefb/zXn2/9m2/P//////////////////////okT8/546/f+eOv3//////8159v/Nefb/zXn2////////////////////////////zXn2/8159v/Nefb//////546/f+bMf7/mzH+//////////////////////////////////////////////////////////////////////+bMf7/lyj+wJco/v/Mk/7////////////////////////////////////////////////////////////Mk///lyj+wJQf/xCUH//AlB///5Qf//+UH///lB///5Qf//+aP///mj///5o///+UH///lB///5Qf//+UH///lB//wJQf/xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAzXn2/5o////Nefb/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAzXn2/wAAAAAAAAAAAAAAAM159v8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAzXn2/wAAAAAAAAAAAAAAAAAAAAAAAAAAzXn2/wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAzXn2/wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADNefb/AAAAAAAAAAAAAAAA+f8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/j8AAP3fAAD77wAA9/cAAA==">'
        yearDiv.insertAdjacentHTML('beforebegin', `<div class="starRatingContainer mediaInfoItem bgm">${bgmIco} 
            <a id="bgmScore" href="${bgmHref}" ${socreIconHrefClass}>${bgmObj.score}</a></div>`);
        console.log('%c%s', 'color: orange;', 'insert bgmScore ', bgmObj.score);
        let tags = bgmObj.tags;
        if (tags && tags.length > 0 && config.tagsNum > 0) {
            tags = tags.filter(name => !config.tagsRegex.test(name)).slice(0, config.tagsNum);
            // let tagsHtml = `<div class="mediaInfoItem">${tags.join(', ')}</div>`
            let tagsHtml = `
  <div class="mediaInfoItem">
    ${tags.map(tag => `<a href="https://bgm.tv/anime/tag/${encodeURIComponent(tag)}" ${socreIconHrefClass} target="_blank">${tag}</a>`).join(', ')}
  </div>
`;

            yearDiv.insertAdjacentHTML('afterend', tagsHtml);

        }
    }
    let tmdbButton = linkZone.querySelector('a[href^="https://www.themovie"]');
    let bgmButton = linkZone.querySelector('a[href^="https://bgm.tv"]');
    if (bgmButton) return;
    let buttonClass = tmdbButton.className;
    let bgmString = `<a is="emby-linkbutton" class="${buttonClass}" href="${bgmHref}" target="_blank"><i class="md-icon button-icon button-icon-left">link</i>Bangumi</a>`;
    tmdbButton.insertAdjacentHTML('beforebegin', bgmString);
}

function checkIsExpire(key, expireDay = 1) {
    let timestamp = localStorage.getItem(key);
    if (!timestamp) return true;
    let expireMs = expireDay * 864E5;
    if (Number(timestamp) + expireMs < Date.now()) {
        localStorage.removeItem(key)
        logger.info(key, 'IsExpire, old', timestamp, 'now', Date.now());
        return true;
    } else {
        return false;
    }

}

async function cleanBgmTags(tags) {
    tags = tags.filter(item => item.count >= 10 && !(config.tagsRegex.test(item.name)));
    let namesList = tags.map(item => item.name);
    return namesList;
}

async function insertBangumiMain(infoTable, linkZone) {
    if (!infoTable || !linkZone) return;
    let mediaInfoItems = infoTable.querySelectorAll('div[class="mediaInfoItem"] > a');
    let isAnime = 0;
    mediaInfoItems.forEach(tagItem => {
        if (tagItem.textContent && tagItem.textContent.search(/动画|Anim/) != -1) { isAnime++ }
    });
    if (isAnime == 0) {
        if (mediaInfoItems.length > 2) return;
        let itemGenres = getVisibleElement(document.querySelectorAll('div[class*="itemGenres"]'));
        if (!itemGenres) return;
        itemGenres = itemGenres.querySelectorAll('a')
        itemGenres.forEach(tagItem => {
            if (tagItem.textContent && tagItem.textContent.search(/动画|Anim/) != -1) { isAnime++ }
        });
        if (isAnime == 0) return;
    };

    let bgmRate = infoTable.querySelector('a#bgmScore');
    if (bgmRate) return;

    let tmdbButton = linkZone.querySelector('a[href^="https://www.themovie"]');
    if (!tmdbButton) return;
    let tmdbId = String(tmdbButton.href.match(/...\d+/));
    tmdbId = tmdbId.startsWith('tv') ? tmdbId : `mov${tmdbId}`

    let year = infoTable.querySelector('div[class="mediaInfoItem"]').textContent.match(/^\d{4}/);
    let expireDay = (Number(year) < new Date().getFullYear() && new Date().getMonth() + 1 != 1) ? 30 : 3

    let tmdbBgmDb = new MyStorage('tmdb|bgm', expireDay);

    let bgmObj = tmdbBgmDb.get(tmdbId);
    if (bgmObj) {
        insertBangumiScore(bgmObj, infoTable, linkZone);
        return;
    }

    let tmdbNotBgmDb = new MyStorage('tmdb|NotBgm', 1);
    if (tmdbNotBgmDb.get(tmdbId)) {
        return;
    }
    let userId = ApiClient._serverInfo.UserId;
    let itemId = /\?id=(\d*)/.exec(window.location.hash)[1];
    let itemInfo = await ApiClient.getItems(userId, {
        'Ids': itemId,
        'Fields': 'OriginalTitle,PremiereDate'
    })
    itemInfo = itemInfo['Items'][0]
    let title = itemInfo.Name;
    let originalTitle = itemInfo.OriginalTitle;

    let splitRe = /[／\/]/;
    if (splitRe.test(originalTitle)) { //纸片人
        logger.info(originalTitle);
        let zprTitle = originalTitle.split(splitRe);
        for (let _i in zprTitle) {
            let _t = zprTitle[_i];
            if (/[あいうえおかきくけこさしすせそたちつてとなにぬねのひふへほまみむめもやゆよらりるれろわをんー]/.test(_t)) {
                originalTitle = _t;
                break
            } else {
                originalTitle = zprTitle[0];
            }
        }
    }

    let premiereDate = new Date(itemInfo.PremiereDate);
    premiereDate.setDate(premiereDate.getDate() - 2);
    let startDate = premiereDate.toISOString().slice(0, 10);
    premiereDate.setDate(premiereDate.getDate() + 4);
    let endDate = premiereDate.toISOString().slice(0, 10);

    logger.info('bgm ->', originalTitle, title, startDate, endDate);
    let bgmInfo;
    for (const _t of [originalTitle, title]) {
        bgmInfo = await getJSON_GM('https://api.bgm.tv/v0/search/subjects?limit=10', JSON.stringify({
            'keyword': _t,
            // "keyword": 'titletitletitletitletitletitletitle',
            'filter': {
                'type': [
                    2
                ],
                'air_date': [
                    `>=${startDate}`,
                    `<${endDate}`
                ],
                'nsfw': true
            }
        }))
        logger.info('bgmInfo', bgmInfo['data'])
        bgmInfo = (bgmInfo['data']) ? bgmInfo['data'][0] : null;
        if (bgmInfo) { break; }
    }

    if (!bgmInfo) {
        tmdbNotBgmDb.set(tmdbId, true);
        logger.error('getJSON_GM not bgmInfo return');
        return;
    };

    let trust = false;
    if (textSimilarity(originalTitle, bgmInfo['name']) < 0.4 && (textSimilarity(title, bgmInfo['name_cn'])) < 0.4
        && (textSimilarity(title, bgmInfo['name'])) < 0.4) {
        tmdbNotBgmDb.set(tmdbId, true);
        logger.error('not bgmObj and title not Similarity, skip');
    } else {
        trust = true
    }
    let score = bgmInfo.score ? bgmInfo.score : bgmInfo.rating?.score;
    let tags = bgmInfo.tags ? await cleanBgmTags(bgmInfo.tags) : [];
    logger.info(bgmInfo)
    bgmObj = {
        id: bgmInfo['id'],
        score: score,
        name: bgmInfo['name'],
        name_cn: bgmInfo['name_cn'],
        trust: trust,
        tags: tags,
    }
    tmdbBgmDb.set(tmdbId, bgmObj)
    insertBangumiScore(bgmObj, infoTable, linkZone);
}

function cleanDoubanError() {
    let expireKey = 'doubanErrorExpireKey';
    let needClean = false;
    if (expireKey in localStorage) {
        if (checkIsExpire(expireKey, 3)) {
            needClean = true;
            localStorage.setItem(expireKey, JSON.stringify(Date.now()));
        }
    } else {
        localStorage.setItem(expireKey, JSON.stringify(Date.now()));
        needClean = true;
    }
    if (!needClean) return;

    let count = 0
    for (let i in localStorage) {
        if (
            i.search(/^tt\d+$/) !== -1 ||
            /^\d{7,9}(Info|Comment)?$/.test(i) ||
            /^(ie|tv)\/\d{4,7}(expire|bgm|NotBgm)$/.test(i) ||
            (i.startsWith('imdb|douban|tt') && localStorage.getItem(i) === '_')
        ) {
            console.log(i);
            count++;
            localStorage.removeItem(i);
        }
    }
    logger.info(`cleanDoubanError done, count=${count}`);
}

setModeSwitchMenu('enableDoubanComment', '豆瓣评论已经', '', '开启')
var runLimit = 50;

async function main() {
    let linkZone = getVisibleElement(document.querySelectorAll('div[class*="linksSection"]'));
    let infoTable = getVisibleElement(document.querySelectorAll('div[class*="flex-grow detailTextContainer"]'));
    if (infoTable && linkZone) {
        if (!infoTable.querySelector('h3.itemName-secondary')) { // not eps page
            await Promise.all([
                insertDoubanMain(linkZone),
                insertBangumiMain(infoTable, linkZone)
            ]);
        } else {
            let bgmIdNode = document.evaluate('//div[contains(text(), "[bgm=")]', document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
            if (bgmIdNode) { insertBangumiByPath(bgmIdNode) };
        }
    }
    if (runLimit > 50) {
        cleanDoubanError();
        runLimit = 0
    }
}

(function loop() {
    setTimeout(async function () {
        // if (runLimit > 5) return;
        await main();
        loop();
        runLimit += 1
    }, 700);
})();
