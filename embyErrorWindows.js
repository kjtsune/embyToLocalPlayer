// ==UserScript==
// @name         embyErrorWindows
// @namespace    http://tampermonkey.net/
// @version      0.1
// @description  auto close emby error windows
// @author       You
// @match        http://192.168.2.22:8096/web/index.html
// @icon         https://www.google.com/s2/favicons?sz=64&domain=emby.media
// @grant        none
// @require      file:///C:/Code/web/embyErrorWindows.js
// ==/UserScript==


function getElementByXpath(expression, contextNode = document) {
    return document.evaluate(expression, contextNode,
        null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
}


setInterval(() => {
    let warnButton = getElementByXpath('//button[@data-id="ok" and contains(text(), "了解")]');
    if (warnButton) { warnButton.click() };
}, 2000);
