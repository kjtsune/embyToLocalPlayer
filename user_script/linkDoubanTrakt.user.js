// ==UserScript==
// @name         linkDoubanTrakt
// @namespace    http://tampermonkey.net/
// @version      2025.09.17
// @description  在豆瓣和 trakt 之间增加跳转链接
// @description:zh-CN 在豆瓣和 trakt 之间增加跳转链接
// @description:en  add trakt link on douban, and vice versa
// @author       Kjtsune
// @match        https://movie.douban.com/top250*
// @match        https://movie.douban.com/subject/*
// @match        https://trakt.tv/movies/*
// @match        https://trakt.tv/shows/*
// @icon         https://www.google.com/s2/favicons?sz=64&domain=douban.com
// @grant        GM.xmlHttpRequest
// @connect      api.douban.com
// @connect      movie.douban.com
// @connect      query.wikidata.org
// @require      https://fastly.jsdelivr.net/gh/kjtsune/UserScripts@a4c9aeba777fdf8ca50e955571e054dca6d1af49/lib/my-storage.js
// @license MIT
// ==/UserScript==
'use strict';

/// <reference path="./lib/my-storage.js" />
/*global MyStorage*/

function isEmpty(s) {
    return !s || s === 'N/A' || s === 'undefined';
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

async function getDoubanAPI(query) {
    return await getJSON_GM(`https://api.douban.com/v2/${query}`, 'apikey=0ab215a8b1977939201640fa14c66bab',
        { 'Content-Type': 'application/x-www-form-urlencoded; charset=utf8', });
}

async function getDoubanId(imdbId,) {

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

    return null;
}

async function getDoubanIdWithStorage(imdbId) {
    let doubanIdDb = new MyStorage('imdb|douban');
    let doubanId = doubanIdDb.get(imdbId);
    if (doubanId) {
        if (doubanId == '_') {
            return null;
        }
        return doubanId;
    }
    doubanId = await getDoubanId(imdbId)
    if (doubanId) {
        doubanIdDb.set(imdbId, doubanId);
        return doubanId;
    } else {
        doubanIdDb.set(imdbId, '_');
    }
}

// Thanks JayXon
function fixImdbLink() {
    let imdbA = document.querySelector('#info > a[href^=https\\:\\/\\/www\\.imdb');
    if (imdbA) return;
    const imdb_text = [...document.querySelectorAll('#info > span.pl')].find(s => s.innerText.trim() == 'IMDb:');
    if (!imdb_text) {
        console.log('IMDb id not available');
        return;
    }
    const text_node = imdb_text.nextSibling;
    const id = text_node.textContent.trim();
    let a = document.createElement('a');
    a.href = 'https://www.imdb.com/title/' + id;
    a.target = '_blank';
    a.appendChild(document.createTextNode(id));
    text_node.replaceWith(a);
    a.insertAdjacentText('beforebegin', ' ');
}

function addTraktLink() {
    if (window.location.host != 'movie.douban.com') { return };
    // if (window.location.host.search(/douban/) == -1) { return };
    let traktA = document.querySelector('#traktLink');
    let imdbA = document.querySelector('#info > a[href^=https\\:\\/\\/www\\.imdb');
    if (!traktA && imdbA) {
        let imdbId = imdbA.textContent
        let traktHtml = `<a id="traktLink" href="https://trakt.tv/search/imdb?query=${imdbId}" target="_blank">  Trakt</a>`
        imdbA.insertAdjacentHTML('afterend', traktHtml);
    }
}

async function addDoubanLink() {
    if (window.location.host != 'trakt.tv') { return };
    if (location.href.contains('seasons')) return;
    let doubanA = document.querySelector('#doubanLink');
    let imdbA = document.querySelector('#external-link-imdb');
    if (!doubanA && imdbA) {
        let imdbId = imdbA.href.split('/').at(-1);
        let doubanId = await getDoubanIdWithStorage(imdbId);
        let linkName = (doubanId) ? 'Douban' : 'Not Douban'
        let douhanHtml = `<a id="doubanLink" href="https://movie.douban.com/subject/${doubanId}/" target="_blank">${linkName}</a>`
        imdbA.insertAdjacentHTML('beforebegin', douhanHtml);
    }

}

function douban_delete_old(item) {
    let year = item.querySelector('p').textContent.split('\n')[2].match(/\d+/)[0]
    if (Number(year) < 2000 || Number(year) > 2010) {
        item.remove()
    }
}

// clean top250

// let movieList = document.querySelectorAll('ol.grid_view > li')
// movieList.forEach(douban_delete_old)

fixImdbLink()
addTraktLink()
addDoubanLink()
