// ==UserScript==
// @name         embyErrorWindows
// @namespace    http://tampermonkey.net/
// @version      0.1.4
// @description  自动关闭 Emby 播放错误 没有兼容的流的窗口提示。
// @description:zh-CN 自动关闭 Emby 播放错误 没有兼容的流的窗口提示。
// @description:en auto close emby error windows.
// @author       Kjtsune
// @match        *://*/web/index.html*
// @icon         https://www.google.com/s2/favicons?sz=64&domain=emby.media
// @license MIT
// ==/UserScript==
'use strict';

async function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

async function reloadPlexPage() {
    let plexPlayerError = document.querySelector('div[class^="PlayerErrorModal-modalHeader"]');
    let plexErrorWindow = document.querySelector('div[class^="Modal-modalContainer"]');
    if (plexPlayerError && plexErrorWindow) {
        await sleep(2000);
        plexPlayerError = document.querySelector('div[class^="PlayerErrorModal-modalHeader"]');
        plexErrorWindow = document.querySelector('div[class^="Modal-modalContainer"]');
        if (plexPlayerError && plexErrorWindow) { location.reload() }
    };

}
let timmer = setInterval(() => {
    let okButtonList = document.querySelectorAll('button[data-id="ok"]');
    for (let index = 0; index < okButtonList.length; index++) {
        const element = okButtonList[index];
        // console.log(element.textContent);
        if (element.textContent.search(/(了解|好的|知道|Got It)/) != -1) {
            element.click();
        }
    }
    let jellyfinSpinner = document.querySelector('div.docspinner');
    if (jellyfinSpinner) { jellyfinSpinner.remove() };
    // let plexCloseButton = document.querySelector('button[class^="ModalContent-closeButton"]');
    reloadPlexPage();
}, 500);
