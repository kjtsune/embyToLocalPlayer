// ==UserScript==
// @name         embyDouban
// @name:zh-CN   embyDouban
// @name:en      embyDouban
// @namespace    https://github.com/kjtsune/embyToLocalPlayer/tree/main/embyDouban
// @version      2024.10.16
// @description  emby 里展示: 豆瓣 Bangumi bgm.tv 评分 链接 (豆瓣评论可关)
// @description:zh-CN emby 里展示: 豆瓣 Bangumi bgm.tv 评分 链接 (豆瓣评论可关)
// @description:en  show douban Bangumi ratings in emby
// @author       Kjtsune
// @match        *://*/web/index.html*
// @icon         https://www.google.com/s2/favicons?sz=64&domain=emby.media
// @grant        GM.xmlHttpRequest
// @grant        GM_registerMenuCommand
// @grant        GM_unregisterMenuCommand
// @connect      api.bgm.tv
// @connect      api.douban.com
// @connect      movie.douban.com
// @license MIT
// ==/UserScript==
'use strict';

setModeSwitchMenu('enableDoubanComment', '豆瓣评论已经', '', '开启')
let enableDoubanComment = (localStorage.getItem('enableDoubanComment') === 'false') ? false : true;

let config = {
    logLevel: 2,
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

function cleanLocalStorage() {
    let count = 0
    for (i in localStorage) {
        if (i.search(/^tt/) != -1 || i.search(/^\d{7}/) != -1) {
            console.log(i);
            count++;
            localStorage.removeItem(i);
        }
    }
    console.log(`remove done, count=${count}`)
}

function getURL_GM(url, data = null) {
    let method = (data) ? 'POST' : 'GET'
    return new Promise(resolve => GM.xmlHttpRequest({
        method: method,
        url: url,
        data: data,
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

async function getJSON_GM(url, data = null) {
    const res = await getURL_GM(url, data);
    if (res) {
        return JSON.parse(res);
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
    if (!id) {
        return;
    }
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
            title: search[0].title,
            sub_title: search[0].sub_title,
        };
    }
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
        let parentNode = (ApiClient._serverVersion.startsWith('4.6')
        ) ? embyComment.parentNode : embyComment.parentNode.parentNode
        parentNode.insertAdjacentHTML('afterend', `<div id="doubanComment"><li>douban comment
        </li>${doubanComment}</li></div>`);
        console.log('%c%s', 'color: orange;', 'insert doubanComment ', doubanId, doubanComment);
    }
}

function insertDoubanScore(doubanId, rating, socreIconHrefClass) {
    rating = rating || localStorage.getItem(doubanId);
    console.log('%c%s', 'color: orange;', 'start ', doubanId, rating);
    let el = getVisibleElement(document.querySelectorAll('a#doubanScore'));
    if (el || !rating) {
        console.log('%c%s', 'color: orange', 'skip add score', el, rating);
        return;
    }
    let yearDiv = getVisibleElement(document.querySelectorAll('div[class="mediaInfoItem"]'));
    if (yearDiv) {
        let doubanIco = `<img style="width:16px;" src="data:image/x-icon;base64,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AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP+RwIn////////////4+/j/GnwK/xF3AP8RdwD/EXcA/xF3AP8afAr/+Pv4////////////kcCJ/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/9Xn0v///////////77auf8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP++2rn////////////V59L/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8rhhz/////////////////erNw/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/3qzcP////////////////8rhhz/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/26sZP////////////////81jCf/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/NYwn/////////////////26sZP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/vdm4////////////5PDi/y+IIP8viCD/L4gg/y+IIP8viCD/L4gg/y+IIP8viCD/5PDi////////////vdm4/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/0+bQ/////////////////////////////////////////////////////////////////////////////////////////////////9Pm0P8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP/T5tD/////////////////////////////////////////////////////////////////////////////////////////////////0+bQ/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/9Pm0P///////////9vq2P+Iu4D/iLuA/4i7gP+Iu4D/iLuA/4i7gP+Iu4D/iLuA/4i7gP+Iu4D/iLuA/4i7gP/b6tj////////////T5tD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/0+bQ////////////tdWw/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/7XVsP///////////9Pm0P8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP/T5tD///////////+11bD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/tdWw////////////0+bQ/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/9Pm0P///////////7XVsP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP+11bD////////////T5tD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/0+bQ////////////tdWw/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/7XVsP///////////9Pm0P8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP/T5tD////////////b6tj/iLuA/4i7gP+Iu4D/iLuA/4i7gP+Iu4D/iLuA/4i7gP+Iu4D/iLuA/4i7gP+Iu4D/2+rY////////////0+bQ/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/9Pm0P/////////////////////////////////////////////////////////////////////////////////////////////////T5tD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/0+bQ/////////////////////////////////////////////////////////////////////////////////////////////////9Pm0P8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/+Lu4P//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////4u7g/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/4u7g///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////i7uD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP/i7uD//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////+Lu4P8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AOYRdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwDmEXcASRF3AOYRdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA/xF3AP8RdwD/EXcA5hF3AEkAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA==">`
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

    if (imdbId in localStorage) {
        var doubanId = localStorage.getItem(imdbId);
        if (!doubanId) { return; }
    } else {
        await getDoubanInfo(imdbId).then(function (data) {
            if (!isEmpty(data)) {
                let doubanId = data.id;
                localStorage.setItem(imdbId, doubanId);
                if (data.rating && !isEmpty(data.rating.average)) {
                    insertDoubanScore(doubanId, data.rating.average, socreIconHrefClass);
                    localStorage.setItem(doubanId, data.rating.average);
                    localStorage.setItem(doubanId + 'Info', JSON.stringify(data));
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
    console.log('%c%o%s', "color:orange;", 'douban id ', doubanId, String(imdbId));
    if (!doubanId) {
        localStorage.setItem(imdbId, '');
        return;
    }
    let buttonClass = imdbButton.className;
    let doubanString = `<a is="emby-linkbutton" class="${buttonClass}" 
    href="https://movie.douban.com/subject/${doubanId}/" target="_blank">
    <i class="md-icon button-icon button-icon-left">link</i>Douban</a>`;
    imdbButton.insertAdjacentHTML('beforebegin', doubanString);
    insertDoubanScore(doubanId, undefined, socreIconHrefClass);
    insertDoubanComment(doubanId);
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
        let bgmIco = `<img style="width:16px;" src="data:image/x-icon;base64,AAABAAEAEBAAAAEAIABoBAAAFgAAACgAAAAQAAAAIAAAAAEAIAAAAAAAQAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAALJu+f//////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAsm75ELJu+cCybvn/sm75/7Ju+f+ybvn//////7Ju+f+ybvn/sm75/7Ju+f+ybvn/sm75/7Ju+f+ybvnAsm75ELJu+cCybvn/sm75/7Ju+f+ybvn/sm75////////////sm75/7Ju+f+ybvn/sm75/7Ju+f+ybvn/sm75/7Ju+cCwaPn/sGj5/9iz/P///////////////////////////////////////////////////////////9iz/P+waPn/rF/6/6xf+v//////////////////////////////////////////////////////////////////////rF/6/6lW+/+pVvv/////////////////////////////////zXn2/////////////////////////////////6lW+/+lTfz/pU38///////Nefb/zXn2/8159v//////zXn2///////Nefb//////8159v/Nefb/zXn2//////+lTfz/okT8/6JE/P//////////////////////2bb8/8159v/Nefb/zXn2/9m2/P//////////////////////okT8/546/f+eOv3//////8159v/Nefb/zXn2////////////////////////////zXn2/8159v/Nefb//////546/f+bMf7/mzH+//////////////////////////////////////////////////////////////////////+bMf7/lyj+wJco/v/Mk/7////////////////////////////////////////////////////////////Mk///lyj+wJQf/xCUH//AlB///5Qf//+UH///lB///5Qf//+aP///mj///5o///+UH///lB///5Qf//+UH///lB//wJQf/xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAzXn2/5o////Nefb/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAzXn2/wAAAAAAAAAAAAAAAM159v8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAzXn2/wAAAAAAAAAAAAAAAAAAAAAAAAAAzXn2/wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAzXn2/wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADNefb/AAAAAAAAAAAAAAAA+f8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/j8AAP3fAAD77wAA9/cAAA==">`
        yearDiv.insertAdjacentHTML('beforebegin', `<div class="starRatingContainer mediaInfoItem bgm">${bgmIco} 
            <a id="bgmScore" href="${bgmHref}" ${socreIconHrefClass}>${bgmObj.score}</a></div>`);
        console.log('%c%s', 'color: orange;', 'insert bgmScore ', bgmObj.score);
    }
    let tmdbButton = linkZone.querySelector('a[href^="https://www.themovie"]');
    let bgmButton = linkZone.querySelector('a[href^="https://bgm.tv"]');
    if (bgmButton) return;
    let buttonClass = tmdbButton.className;
    let bgmString = `<a is="emby-linkbutton" class="${buttonClass}" href="${bgmHref}" target="_blank"><i class="md-icon button-icon button-icon-left">link</i>Bangumi</a>`;
    tmdbButton.insertAdjacentHTML('beforebegin', bgmString);
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

function checkIsExpire(key, expireDay = 1) {
    let timestamp = localStorage.getItem(key);
    if (!timestamp) return true;
    let expireMs = expireDay * 864E5;
    if (Number(timestamp) + expireMs < Date.now()) {
        localStorage.removeItem(key)
        logger.info(key, "IsExpire, old", timestamp, "now", Date.now());
        return true;
    } else {
        return false;
    }

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
    let tmdbId = tmdbButton.href.match(/...\d+/);

    let tmdbExpireKey = tmdbId + 'expire'
    let year = infoTable.querySelector('div[class="mediaInfoItem"]').textContent.match(/^\d{4}/);
    let expireDay = (Number(year) < new Date().getFullYear() && new Date().getMonth() + 1 != 1) ? 30 : 3
    let needUpdate = false;
    if (tmdbExpireKey in localStorage) {
        if (checkIsExpire(tmdbExpireKey, expireDay)) {
            needUpdate = true;
            localStorage.setItem(tmdbExpireKey, JSON.stringify(Date.now()));
        }
    } else {
        localStorage.setItem(tmdbExpireKey, JSON.stringify(Date.now()));
    }


    let tmdbBgmKey = tmdbId + 'bgm';
    let bgmObj = localStorage.getItem(tmdbBgmKey);
    if (bgmObj && !needUpdate) {
        bgmObj = JSON.parse(bgmObj)
        insertBangumiScore(bgmObj, infoTable, linkZone);
        return;
    }

    let tmdbNotBgmKey = tmdbId + 'NotBgm';
    if (!checkIsExpire(tmdbNotBgmKey)) {
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

    logger.info('bgm ->', originalTitle, startDate, endDate);
    let bgmInfo = await getJSON_GM(`https://api.bgm.tv/v0/search/subjects?limit=10`, JSON.stringify({
        "keyword": originalTitle,
        // "keyword": 'titletitletitletitletitletitletitle',
        "filter": {
            "type": [
                2
            ],
            "air_date": [
                `>=${startDate}`,
                `<${endDate}`
            ],
            "nsfw": true
        }
    }))
    logger.info('bgmInfo', bgmInfo['data'])
    bgmInfo = (bgmInfo['data']) ? bgmInfo['data'][0] : null;
    if (!bgmInfo) {
        localStorage.setItem(tmdbNotBgmKey, JSON.stringify(Date.now()));
        logger.error('getJSON_GM not bgmInfo return');
        return;
    };

    let trust = false;
    if (textSimilarity(originalTitle, bgmInfo['name']) < 0.4 && (textSimilarity(title, bgmInfo['name_cn'])) < 0.4
        && (textSimilarity(title, bgmInfo['name'])) < 0.4) {
        localStorage.setItem(tmdbNotBgmKey, JSON.stringify(Date.now()));
        logger.error('not bgmObj and title not Similarity, skip');
    } else {
        trust = true
    }
    logger.info(bgmInfo)
    bgmObj = {
        id: bgmInfo['id'],
        score: bgmInfo['score'],
        name: bgmInfo['name'],
        name_cn: bgmInfo['name_cn'],
        trust: trust,
    }
    localStorage.setItem(tmdbBgmKey, JSON.stringify(bgmObj));
    insertBangumiScore(bgmObj, infoTable, linkZone);
}

function cleanDoubanError() {
    let expireKey = 'doubanErrorExpireKey';
    let needClean = false;
    if (expireKey in localStorage) {
        if (checkIsExpire(expireKey, 3)) {
            needClean = true
            localStorage.setItem(expireKey, JSON.stringify(Date.now()));
        }
    } else {
        localStorage.setItem(expireKey, JSON.stringify(Date.now()));
    }
    if (!needClean) return;

    let count = 0
    for (let i in localStorage) {
        if (i.search(/^tt\d+/) != -1 && localStorage.getItem(i) === '') {
            console.log(i);
            count++;
            localStorage.removeItem(i);
        }
    }
    logger.info(`cleanDoubanError done, count=${count}`);
}

var runLimit = 50;

async function main() {
    let linkZone = getVisibleElement(document.querySelectorAll('div[class*="linksSection"]'));
    let infoTable = getVisibleElement(document.querySelectorAll('div[class*="flex-grow detailTextContainer"]'));
    if (infoTable && linkZone) {
        if (!infoTable.querySelector('h3.itemName-secondary')) { // not eps page
            insertDoubanMain(linkZone);
            await insertBangumiMain(infoTable, linkZone)
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
