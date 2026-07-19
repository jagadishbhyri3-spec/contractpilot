document.addEventListener('DOMContentLoaded', () => {
    const token = localStorage.getItem('token');

    const navLogin    = document.getElementById('navLogin');
    const navRegister = document.getElementById('navRegister');
    const navDashboard = document.getElementById('navDashboard');
    const navUpload   = document.getElementById('navUpload');
    const navLogout   = document.getElementById('navLogout');

    if (token) {
        // User is logged in
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
        // User is logged out
        if (navDashboard) navDashboard.style.display = 'none';
        if (navUpload)   navUpload.style.display = 'none';
        if (navLogout)   navLogout.style.display = 'none';
    }

    // ═══════════════════════════════════════════════════════════════
    // FIX: Remove target="_blank" from all internal links
    // This prevents links from opening in new tabs
    // ═══════════════════════════════════════════════════════════════

    document.querySelectorAll('a').forEach(link => {
        const href = link.getAttribute('href') || '';

        // Only fix internal links (not external URLs like https://...)
        if (href.startsWith('/') || href.startsWith('#') || href === '' || !href.includes('://')) {
            link.removeAttribute('target');

            // Also prevent any click handlers from opening new tabs
            link.addEventListener('click', function(e) {
                // If it's a real link (not a # anchor for JS), let it navigate normally
                if (href && href !== '#' && !href.startsWith('#')) {
                    // Remove target="_blank" just before navigation
                    this.removeAttribute('target');
                }
            });
        }
    });
});
