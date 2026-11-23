import CONFIG from '../config.js';

// 离线双击（file://）时，API_BASE 默认指向本地后端
if (location.protocol === 'file:' && !CONFIG.API_BASE) {
  CONFIG.API_BASE = 'http://localhost:8000';
}

function api(path, opts) {
  opts = opts || {};
  return fetch(CONFIG.API_BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  }).then((r) => r.json());
}

export { CONFIG, api };
