// ==UserScript==
// @name         embyToLocalPlayer
// @name:en      embyToLocalPlayer
// @name:zh-CN   embyToLocalPlayer
// @namespace    http://tampermonkey.net/
// @version      0.1
// @description  Require python and set up. If you use mpv, will update watch history to emby server.
// @description:zh-CN 需要pthon和配置本地文件。若用mpv播放，可更新服务器观看进度。
// @author       Kjtsune
// @match        http://192.168.2.22:8096/web/index.html
// @icon         https://www.google.com/s2/favicons?sz=64&domain=emby.media
// @grant        unsafeWindow
// @run-at       document-start
// @require      file:///C:/Code/web/embyToLocalPlayer.js
// ==/UserScript==

const originFetch = fetch;
unsafeWindow.fetch = (...arg) => {
    if (arg[0].indexOf('/PlaybackInfo?UserId') > -1 && arg[0].indexOf('IsPlayback=true') > -1) {
        embyToLocalPlayer(arg[0])
        return ''
    }
    else if (arg[0].indexOf('/dialog.template.html') != -1) {
        return
    }
    else {
        return originFetch(...arg);
    }
}


async function getItemInfo(itemInfoUrl) {
    let response = await fetch(itemInfoUrl);
    if (response.ok) {
        return await response.json();
    } else {
        throw new Error(response.statusText);
    }
}


async function embyToLocalPlayer(itemInfoUrl) {
    // let data = await getEmbyMediaData(itemInfoUrl);
    let data = {
        data: await getItemInfo(itemInfoUrl),
        url: itemInfoUrl
    };
    fetch('http://127.0.0.1:58000/embyToLocalPlayer/', {
        method: 'POST',
        body: JSON.stringify(data)
    })
}