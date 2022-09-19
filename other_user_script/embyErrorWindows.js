// ==UserScript==
// @name         embyErrorWindows
// @namespace    http://tampermonkey.net/
// @version      0.1.3
// @description  auto close emby error windows
// @author       Kjtsune
// @match        *://*/web/index.html*
// @icon         https://www.google.com/s2/favicons?sz=64&domain=emby.media
// @license MIT
// ==/UserScript==
'use strict';

setInterval(() => {
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
}, 500);
