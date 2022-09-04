// ==UserScript==
// @name         embyErrorWindows
// @namespace    http://tampermonkey.net/
// @version      0.1.2
// @description  auto close emby error windows
// @author       Kjtsune
// @match        *://*/web/index.html*
// @icon         https://www.google.com/s2/favicons?sz=64&domain=emby.media
// @grant        none
// @license MIT
// ==/UserScript==
'use strict';

function getElementByXpath(expression, contextNode = document) {
    return document.evaluate(expression, contextNode,
        null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
}

setInterval(() => {
    let warnButton = getElementByXpath('//button[@data-id="ok" and contains(text(), "了解")] | //button[@data-id="ok" and contains(text(), "好的")]');
    if (warnButton) { warnButton.click() };
}, 500);
