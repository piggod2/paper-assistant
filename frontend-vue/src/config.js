// 论文智助 — 前端配置
// 切环境只改这一行，所有 API 走 CONFIG.API_BASE + /api/*
const CONFIG = {
    API_BASE: '',
    APP_NAME: '论文智助',
    SLOGAN: '不替你改写，替你揪出 AI 味',
    SHARE_URL_BASE: window.location.origin,

    // WorkBuddy 免密钥大模型（用于自由问答兜底）
    // publishableKey 只标识应用、本身无权限，可放在前端源码；服务端按 Origin 精确校验
    CLOUD_ENDPOINT: 'https://paper-assistant-58330.app.workbuddy.host',
    CLOUD_PUBLISHABLE_KEY: 'wbpk_dkS2n4X8lkzEQ3k5obpema_SQIkaF35LDjRM0iG57E1Mo8omOWPqqZA',
    CLOUD_OAUTH_RELAY: 'https://www.workbuddy.cn/v2/as/genie-baas/oauth',
};

export default CONFIG;
