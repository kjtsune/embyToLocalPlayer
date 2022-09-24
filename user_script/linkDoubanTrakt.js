// ==UserScript==
// @name         linkDoubanTrakt
// @namespace    http://tampermonkey.net/
// @version      0.1
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
// @require      file:///C:/Code/web/linkDoubanTrakt.js
// @license MIT
// ==/UserScript==
"use strict";


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

async function getDoubanId(imdbId) {
    const search = await getJSON_GM(`https://movie.douban.com/j/subject_suggest?q=${imdbId}`);
    if (search && search.length > 0 && search[0].id) {
        return search[0].id
    }
}

function addTraktLink() {
    if (window.location.host != 'movie.douban.com') { return };
    // if (window.location.host.search(/douban/) == -1) { return };
    let traktA = document.querySelector('#traktLink');
    let imdbA = document.querySelector('#info > a[href^=https\\:\\/\\/www\\.imdb');
    if (!traktA && imdbA) {
        let imdbId = imdbA.textContent
        let traktHtml = `<a id="traktLink" href="https://trakt.tv/search/imdb?query=${imdbId}" target="_blank">  Trakt</a>`
        imdbA.insertAdjacentHTML("afterend", traktHtml);
    }
}

async function addDoubanLink() {
    if (window.location.host != 'trakt.tv') { return };
    let doubanA = document.querySelector('#doubanLink');
    let imdbA = document.querySelector('#external-link-imdb');
    if (!doubanA && imdbA) {
        let imdbId = imdbA.href.split('/').at(-1);
        let doubanId = await getDoubanId(imdbId);
        let douhanHtml = `<a id="doubanLink" href="https://movie.douban.com/subject/${doubanId}/" target="_blank">Douban</a>`
        imdbA.insertAdjacentHTML("beforebegin", douhanHtml);
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

addTraktLink()
addDoubanLink()
