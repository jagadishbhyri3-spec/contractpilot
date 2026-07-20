// AGGRESSIVE FIX: Prevent ALL links from opening in new tabs
// This runs immediately, before DOMContentLoaded

(function() {
    'use strict';

    // Function to strip target="_blank" from all links
    function fixLinks() {
        var links = document.querySelectorAll('a[target="_blank"]');
        for (var i = 0; i < links.length; i++) {
            links[i].removeAttribute('target');
        }
    }

    // Run immediately if DOM is ready
    if (document.readyState === 'complete' || document.readyState === 'interactive') {
        fixLinks();
    }

    // Also run on DOMContentLoaded
    document.addEventListener('DOMContentLoaded', fixLinks);

    // Also run after a short delay to catch any dynamically added links
    setTimeout(fixLinks, 100);
    setTimeout(fixLinks, 500);
    setTimeout(fixLinks, 1000);

    // MOST IMPORTANT: Intercept all click events on the document
    // This catches clicks BEFORE the browser processes them
    document.addEventListener('click', function(e) {
        var target = e.target;

        // Walk up the DOM to find if a link was clicked
        while (target && target !== document.body) {
            if (target.tagName === 'A') {
                var href = target.getAttribute('href') || '';

                // Check if it's an internal link
                var isInternal = href.indexOf('://') === -1 || 
                                 href.indexOf(window.location.host) !== -1 ||
                                 href.startsWith('/') ||
                                 href.startsWith('#');

                if (isInternal) {
                    // Force same-tab navigation
                    target.removeAttribute('target');

                    // If it's a real link (not just #), let it navigate normally
                    if (href && href !== '#' && !href.startsWith('#')) {
                        // Prevent any default new-tab behavior
                        e.stopPropagation();
                    }
                }
                break;
            }
            target = target.parentElement;
        }
    }, true); // Use capture phase to intercept before other handlers

})();

// Original auth logic
document.addEventListener('DOMContentLoaded', () => {
    const token = localStorage.getItem('token');

    const navLogin    = document.getElementById('navLogin');
    const navRegister = document.getElementById('navRegister');
    const navDashboard = document.getElementById('navDashboard');
    const navUpload   = document.getElementById('navUpload');
    const navLogout   = document.getElementById('navLogout');

    if (token) {
        if (navLogin)    navLogin.style.display = 'none';
        if (navRegister) navRegister.style.display = 'none';
        if (navDashboard) navDashboard.style.display = 'inline';
        if (navUpload)   navUpload.style.display = 'inline';
        if (navLogout) {
            navLogout.style.display = 'inline';
            navLogout.addEventListener('click', (e) => {
                e.preventDefault();
                localStorage.removeItem('token');
                window.location.href = '/';
            });
        }
    } else {
        if (navDashboard) navDashboard.style.display = 'none';
        if (navUpload)   navUpload.style.display = 'none';
        if (navLogout)   navLogout.style.display = 'none';
    }
});
