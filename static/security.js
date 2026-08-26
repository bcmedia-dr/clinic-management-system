(function () {
    'use strict';

    function escapeHtml(value) {
        return String(value == null ? '' : value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function csrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.content : '';
    }

    const originalFetch = window.fetch.bind(window);
    window.fetch = function (input, init) {
        const options = Object.assign({}, init || {});
        const method = String(options.method || 'GET').toUpperCase();
        const target = typeof input === 'string' ? new URL(input, window.location.href) : new URL(input.url, window.location.href);
        if (target.origin === window.location.origin && !['GET', 'HEAD', 'OPTIONS'].includes(method)) {
            const headers = new Headers(options.headers || (typeof input !== 'string' ? input.headers : undefined));
            headers.set('X-CSRF-Token', csrfToken());
            options.headers = headers;
        }
        return originalFetch(input, options);
    };

    window.Security = Object.freeze({ escapeHtml: escapeHtml, csrfToken: csrfToken });
    window.secureLogout = async function () {
        try {
            await window.fetch('/logout', { method: 'POST' });
        } finally {
            window.location.href = '/login';
        }
    };
})();
