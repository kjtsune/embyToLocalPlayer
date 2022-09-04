// ==UserScript==
// @name         embyDouban
// @name:zh-CN   embyDouban
// @name:en      embyDouban
// @namespace    https://github.com/kjtsune/embyToLocalPlayer/tree/main/embyDouban
// @version      0.1.1
// @description  emby 里展示豆瓣 评分 链接 评论(可关)
// @description:zh-CN  emby 里展示豆瓣 评分 链接 评论(可关)
// @description:en  show douban ratings and comment[optional] on emby
// @author       Kjtsune
// @match        *://*/web/index.html*
// @icon         https://www.google.com/s2/favicons?sz=64&domain=emby.media
// @grant        GM.xmlHttpRequest
// @grant        GM_registerMenuCommand
// @grant        GM_unregisterMenuCommand
// @connect      api.douban.com
// @connect      movie.douban.com
// @license MIT
// ==/UserScript==
'use strict';

setModeSwitchMenu('enableDoubanComment', '豆瓣评论已经', '', '开启')
let enableDoubanComment = (localStorage.getItem('enableDoubanComment') === 'false') ? false : true;

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

function getURL_GM(url) {
    return new Promise(resolve => GM.xmlHttpRequest({
        method: 'GET',
        url: url,
        onload: function (response) {
            if (response.status >= 200 && response.status < 400) {
                resolve(response.responseText);
            } else {
                console.error(`Error getting ${url}:`, response.status, response.statusText, response.responseText);
                resolve();
            }
        },
        onerror: function (response) {
            console.error(`Error during GM.xmlHttpRequest to ${url}:`, response.statusText);
            resolve();
        }
    }));
}

async function getJSON_GM(url) {
    const data = await getURL_GM(url);
    if (data) {
        return JSON.parse(data);
    }
}

// async function getJSONP_GM(url) {
//     const data = await getURL_GM(url);
//     if (data) {
//         const end = data.lastIndexOf(')');
//         const [, json] = data.substring(0, end).split('(', 2);
//         return JSON.parse(json);
//     }
// }

async function getJSON(url) {
    try {
        const response = await fetch(url);
        if (response.status >= 200 && response.status < 400)
            return await response.json();
        console.error(`Error fetching ${url}:`, response.status, response.statusText, await response.text());
    }
    catch (e) {
        console.error(`Error fetching ${url}:`, e);
    }
}

async function getDoubanInfo(id) {
    // TODO: Remove this API completely if it doesn't come back.
    // const data = await getJSON_GM(`https://api.douban.com/v2/movie/imdb/${id}?apikey=123456`);
    // if (data) {
    //     if (isEmpty(data.alt))
    //         return;
    //     const url = data.alt.replace('/movie/', '/subject/') + '/';
    //     return { url, rating: data.rating };
    // }
    // Fallback to search.
    const search = await getJSON_GM(`https://movie.douban.com/j/subject_suggest?q=${id}`);
    if (search && search.length > 0 && search[0].id) {
        const abstract = await getJSON_GM(`https://movie.douban.com/j/subject_abstract?subject_id=${search[0].id}`);
        const average = abstract && abstract.subject && abstract.subject.rate ? abstract.subject.rate : '?';
        const comment = abstract && abstract.subject && abstract.subject.short_comment && abstract.subject.short_comment.content;
        return {
            id: search[0].id,
            comment: comment,
            // url: `https://movie.douban.com/subject/${search[0].id}/`,
            rating: { numRaters: '', max: 10, average },
            // title: search[0].title,
        };
    }
}

function isEmpty(s) {
    return !s || s === 'N/A' || s === 'undefined';
}

async function insertDoubanButton(correctZone) {
    if (isEmpty(correctZone)) { return; }
    let doubanButton = correctZone.querySelector('a[href*="douban.com"]');
    let imdbButton = correctZone.querySelector('a[href^="https://www.imdb"]');
    if (doubanButton || !imdbButton) { return; }
    let imdbId = imdbButton.href.match(/tt\d+/);
    if (imdbId in localStorage) {
        var doubanId = localStorage.getItem(imdbId);
    } else {
        await getDoubanInfo(imdbId).then(function (data) {
            if (!isEmpty(data)) {
                let doubanId = data.id;
                localStorage.setItem(imdbId, doubanId);
                if (data.rating && !isEmpty(data.rating.average)) {
                    insertDoubanScore(doubanId, data.rating.average);
                    localStorage.setItem(doubanId, data.rating.average);
                }
                if (enableDoubanComment) {
                    insertDoubanComment(doubanId, data.comment);
                    localStorage.setItem(doubanId + 'Comment', data.comment);
                }
            }
            console.log('%c%o%s', 'background:yellow;', data, ' result and send a requests')
        });
        var doubanId = localStorage.getItem(imdbId);
    }
    console.log('%c%o%s', "color:orange;", 'douban id ', doubanId)
    if (!doubanId) {
        localStorage.setItem(imdbId, '');
        return;
    }
    let doubanString = `<a is="emby-linkbutton" class="raised item-tag-button nobackdropfilter emby-button" href="https://movie.douban.com/subject/${doubanId}/" target="_blank"><i class="md-icon button-icon button-icon-left">link</i>Douban</a>`;
    imdbButton.insertAdjacentHTML('beforebegin', doubanString);
    insertDoubanScore(doubanId);
    insertDoubanComment(doubanId);
}

function insertDoubanComment(doubanId, doubanComment) {
    console.log('%c%o%s', "color:orange;", 'start add comment ', doubanId)
    if (!enableDoubanComment) { return; }
    let commentKey = `${doubanId}Comment`;
    doubanComment = doubanComment || localStorage.getItem(commentKey);
    let el = getVisibleElement(document.querySelectorAll('div#doubanComment'));
    if (el || isEmpty(doubanComment)) {
        console.log('%c%s', 'color: orange', 'skip add doubanComment', el, doubanComment);
        return;
    }
    let embyComment = getVisibleElement(document.querySelectorAll('div.overview-text'));
    if (embyComment) {
        embyComment.parentNode.parentNode.insertAdjacentHTML('afterend', `<div id="doubanComment"><li>douban comment
        </li>${doubanComment}</li></div>`);
        console.log('%c%s', 'color: orange;', 'insert doubanComment ', doubanId, doubanComment);
    }
}

function insertDoubanScore(doubanId, rating) {
    rating = rating || localStorage.getItem(doubanId);
    console.log('%c%s', 'color: orange;', 'start ', doubanId, rating);
    let el = getVisibleElement(document.querySelectorAll('a#doubanScore'));
    if (el || !rating) {
        console.log('%c%s', 'color: orange', 'skip add score', el, rating);
        return;
    }
    let embyRate = getVisibleElement(document.querySelectorAll('div.starRatingContainer.mediaInfoItem'));
    if (embyRate) {
        embyRate.insertAdjacentHTML('afterbegin', `<a id="doubanScore">${rating}</a>`);
        console.log('%c%s', 'color: orange;', 'insert score ', doubanId, rating);
    }
    console.log('%c%s', 'color: orange;', 'finish ', doubanId, rating);
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

function cleanLocalStorage() {
    for (i in localStorage) {
        if (i.search(/^tt/) != -1 || i.search(/\d{8}/) != -1) {
            console.log(i);
            localStorage.removeItem(i);
        }
    }
}

function isHidden(el) {
    return (el.offsetParent === null);
}

function insertBangumiButton(idNode) {
    let el = getVisibleElement(document.querySelectorAll('a#bangumibutton'));
    if (el) { return; }
    let id = idNode.textContent.match(/(?<=bgm\=)\d+/);
    let bgmHtml = `<a id="bangumibutton" is="emby-linkbutton" class="raised item-tag-button nobackdropfilter emby-button" href="https://bgm.tv/subject/${id}" target="_blank"><i class="md-icon button-icon button-icon-left">link</i>Bangumi</a>`
    idNode.insertAdjacentHTML('beforebegin', bgmHtml);
}

setInterval(() => {
    let linkZone = document.querySelectorAll('div[class="verticalSection linksSection verticalSection-extrabottompadding"]');
    if (linkZone.length > 0) {
        insertDoubanButton(getVisibleElement(linkZone));
    }
    let bgmIdNode = document.evaluate('//div[contains(text(), "[bgm=")]', document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
    if (bgmIdNode) { insertBangumiButton(bgmIdNode) };
}, 2000);
