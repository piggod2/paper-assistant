# -*- coding: utf-8 -*-
"""
论文智助 — 部署专用启动入口（供 WorkBuddy 发布 / 云沙盒使用）
与本地 start.py 的区别：无浏览器弹窗、无 input 阻塞、无 PID 文件、无本地路径依赖。
只做一件事：加载 .env → 导入 app → 监听 PORT + 0.0.0.0。
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, 'backend'))

# 加载环境变量（.env 不存在也不报错）
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, '.env'))
except Exception:
    pass

from server import app
import uvicorn

port = int(os.getenv('PORT', 8000))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
