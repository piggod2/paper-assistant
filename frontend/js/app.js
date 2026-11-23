(function () {
    const { createApp, onMounted } = Vue;

    const state = PA.createState();
    const applySettings = PA.useSettings(state);
    const derived = PA.useDerived(state);
    const actions = PA.useActions(state);
    const qa = PA.useQa();

    createApp({
        setup() {
            onMounted(function () {
                applySettings();

                const p = new URLSearchParams(location.search);
                const s = p.get('s');
                if (s) {
                    try {
                        const d = JSON.parse(new TextDecoder().decode(
                            Uint8Array.from(atob(s.replace(/-/g, '+').replace(/_/g, '/')), c => c.charCodeAt(0))
                        ));
                        state.text.value = d.text || '';
                        state.polished.value = d.polished || '';
                        state.shareBanner.value = d.from ? `${d.from}分享的一份检测结果 · ${d.date}` : '分享的检测结果';
                    } catch (e) { }
                }

                state.shareCode.value = p.get('sharecode');
                if (state.shareCode.value) actions.fetchShare();

                window.addEventListener('online', function () { state.offline.value = false });
                window.addEventListener('offline', function () { state.offline.value = true });

                qa.bindResize();
            });

            return {
                CONFIG: PA.CONFIG,
                ...state,
                ...derived,
                ...actions,
                ...qa,
            };
        }
    }).mount('#app');
})();