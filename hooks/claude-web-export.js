// ==UserScript==
// @name         DevMemory Claude Web Exporter
// @namespace    https://github.com/Mysticbirdie/DevMemory
// @version      1.0
// @description  Auto-export Claude Projects, Artifacts, and Canvas to DevMemory
// @match        https://claude.ai/*
// @match        https://*.claude.ai/*
// @grant        GM_download
// @grant        GM_notification
// ==/UserScript==

(function() {
    'use strict';

    // DevMemory export paths (adjust if your Downloads structure differs)
    const EXPORT_PATHS = {
        projects: 'Claude/Projects',
        artifacts: 'Claude/Artifacts',
        canvas: 'Claude/Canvas'
    };

    // Monitor for artifact creation
    function watchForArtifacts() {
        const observer = new MutationObserver((mutations) => {
            for (const mutation of mutations) {
                for (const node of mutation.addedNodes) {
                    if (node.nodeType === Node.ELEMENT_NODE) {
                        // Detect artifact containers
                        if (node.querySelector('[data-testid="artifact"]') ||
                            node.classList?.contains('artifact') ||
                            node.querySelector('.claude-artifact')) {
                            console.log('[DevMemory] Artifact detected');
                            notifyExport('Artifact detected! Click "View source" to export.');
                        }

                        // Detect canvas
                        if (node.querySelector('[data-testid="canvas"]') ||
                            node.classList?.contains('canvas')) {
                            console.log('[DevMemory] Canvas detected');
                            notifyExport('Canvas detected! Use Share → Export to save.');
                        }
                    }
                }
            }
        });

        observer.observe(document.body, { childList: true, subtree: true });
    }

    // Add export helper buttons
    function addExportButtons() {
        // Check if we're on a project page
        if (window.location.href.includes('/project/')) {
            addProjectExportButton();
        }
    }

    function addProjectExportButton() {
        const btn = document.createElement('button');
        btn.innerText = '📥 Export to DevMemory';
        btn.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 9999;
            background: #d97757;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-family: sans-serif;
            font-size: 14px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        `;
        btn.onclick = () => {
            notifyExport('Export the project ZIP and save to ~/Downloads/Claude/Projects/');
        };
        document.body.appendChild(btn);
    }

    function notifyExport(message) {
        if (typeof GM_notification !== 'undefined') {
            GM_notification({
                title: 'DevMemory Export',
                text: message,
                timeout: 5000
            });
        } else {
            console.log('[DevMemory]', message);
            // Show inline notification
            const toast = document.createElement('div');
            toast.innerText = message;
            toast.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                background: #333;
                color: white;
                padding: 12px 20px;
                border-radius: 8px;
                z-index: 99999;
                font-family: sans-serif;
                font-size: 13px;
                max-width: 300px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            `;
            document.body.appendChild(toast);
            setTimeout(() => toast.remove(), 5000);
        }
    }

    // Initialize
    console.log('[DevMemory] Claude Web exporter loaded');
    watchForArtifacts();
    addExportButtons();

    // Re-check on navigation (Claude is SPA)
    let lastUrl = location.href;
    new MutationObserver(() => {
        const url = location.href;
        if (url !== lastUrl) {
            lastUrl = url;
            addExportButtons();
        }
    }).observe(document, { subtree: true, childList: true });

})();
