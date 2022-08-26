// ==UserScript==
// @name         embyErrorWindows
// @namespace    http://tampermonkey.net/
// @version      0.1.1
// @description  auto close emby error windows
// @author       Kjtsune
// @include      */web/index.html*
// @icon         https://www.google.com/s2/favicons?sz=64&domain=emby.media
// @grant        none
// ==/UserScript==
'use strict';

function getElementByXpath(expression, contextNode = document) {
    return document.evaluate(expression, contextNode,
        null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
}


setInterval(() => {
    let warnButton = getElementByXpath('//button[@data-id="ok" and contains(text(), "了解")]');
    if (warnButton) { warnButton.click() };
}, 500);
