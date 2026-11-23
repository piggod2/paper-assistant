import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { rmSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = dirname(fileURLToPath(import.meta.url));

// 构建前只清空 assets/，避免旧哈希产物堆积；
// 保留 frontend/ 下的 legacy/、agent.html、config.js 等非构建文件
function cleanAssetsPlugin() {
  return {
    name: 'clean-assets',
    apply: 'build',
    buildStart() {
      rmSync(resolve(root, '../frontend/assets'), { recursive: true, force: true });
    },
  };
}

// 构建产物直接输出到 ../frontend/，让后端（挂载 frontend/）无需改动
export default defineConfig({
  plugins: [vue(), cleanAssetsPlugin()],
  build: {
    outDir: '../frontend',
    emptyOutDir: false, // 不清空，保留 legacy/ 备份和 agent.html
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    // 开发模式下把 /api 转发给本地后端（8000），避免跨端口 404
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
});