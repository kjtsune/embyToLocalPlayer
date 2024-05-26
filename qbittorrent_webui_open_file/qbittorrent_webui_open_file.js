// ==UserScript==
// @name         qbittorrent_webui_open_file
// @namespace    https://github.com/kjtsune/embyToLocalPlayer/tree/main/qbittorrent_webui_open_file
// @version      0.3
// @description  在 qBittorrent WebUI 里打开文件夹或者播放文件。
// @description:zh-CN 在 qBittorrent WebUI 里打开文件夹或者播放文件。
// @description:en  open folder or play media file from qb webui.
// @author       Kjtsune
// @match        http://127.0.0.1:88*
// @include      *192.168.*:88*
// @icon         https://www.google.com/s2/favicons?sz=64&domain=qbittorrent.org
// @grant        GM.xmlHttpRequest
// @license MIT
// ==/UserScript==
'use strict';

function checkAndAddElement() {
    let infoTable = document.querySelector('div.propertiesTabContent');
    let openButton = document.querySelector('a#openButton');
    if (infoTable && !openButton) {
        let savePath = infoTable.querySelector('#save_path');
        savePath.insertAdjacentHTML('beforeBegin',
            `<a id="openButton">打开</a> <span> </span> <a id="playButton">播放</a>`);
        let openButton = infoTable.querySelector('a#openButton');
        let playButton = infoTable.querySelector('a#playButton');
        openButton.addEventListener("click", openFolderFn, false);
        playButton.addEventListener("click", playMediaFile, false);
    }
}

function openFolderFn() {
    sendTorrentInfoAndOperate('openFolder')
}

function playMediaFile() {
    sendTorrentInfoAndOperate('playMediaFile')
}

async function sendTorrentInfoAndOperate(operate) {
    let data = await getTorrentInfo();
    let result = {
        info: data[0],
        file: data[1],
        href: window.location.href
    }
    sendDataToLocalServer(result, operate)
}

async function getTorrentInfo() {
    let torrentHashList = document.querySelectorAll('td[id^=torrent_hash]');
    for (let index = 0; index < torrentHashList.length; index++) {
        const torrentHash = torrentHashList[index];
        var hashText = torrentHash.textContent;
        console.log('index', index, 'hash', hashText)
        if (hashText.length > 15) break;
    }

    let info = await fetch(`${window.location.href}api/v2/torrents/info?hashes=${hashText}`)
        .then(r => r.json());
    let fileList = await fetch(`${window.location.href}api/v2/torrents/files?hash=${hashText}`)
        .then(r => r.json());
    let result = [info, fileList]
    return result
}

function sendDataToLocalServer(data, path) {
    let url = `http://127.0.0.1:58000/${path}/`
    GM.xmlHttpRequest({
        method: "POST",
        url: url,
        data: JSON.stringify(data),
        headers: {
            "Content-Type": "application/json"
        }
    });
}

setInterval(() => {
    checkAndAddElement();
}, 2000);
