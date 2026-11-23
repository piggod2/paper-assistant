window.PA = window.PA || {};

PA.CONFIG = (typeof CONFIG !== 'undefined' && CONFIG)
    ? Object.assign({}, CONFIG)
    : { API_BASE: '', APP_NAME: '论文智助', SLOGAN: '不替你改写，替你揪出 AI 味', SHARE_URL_BASE: window.location.origin };

if (location.protocol === 'file:' && !PA.CONFIG.API_BASE) {
    PA.CONFIG.API_BASE = 'http://localhost:8000';
}

PA.api = function (path, opts) {
    opts = opts || {};
    return fetch(PA.CONFIG.API_BASE + path, {
        headers: { 'Content-Type': 'application/json' },
        ...opts,
    }).then(function (r) { return r.json(); });
};