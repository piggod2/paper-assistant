# -*- coding: utf-8 -*-
"""
论文智助 一键启动 — 双击此文件
主线程直接运行 uvicorn，任何异常都会清晰打印，便于排查。
"""
import os
import sys
import time
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, 'backend'))
os.chdir(ROOT)

# 启动前打印环境信息，便于排查（flush 保证实时显示）
def _log(msg=""):
    print(msg, flush=True)

_log("=" * 50)
_log("  论文智助 启动中 ...")
_log("  Python: " + sys.version.split()[0])
_log("  项目目录: " + ROOT)
_log("=" * 50)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, '.env'))
    _log("  [OK] 已加载 .env 配置")
except Exception as e:
    _log("  [WARN] 加载 .env 失败: " + str(e))

try:
    from server import app
    import uvicorn
    _log("  [OK] 已导入后端服务")
except Exception as e:
    _log("  [ERROR] 导入后端失败: " + str(e))
    _log("  请确认已安装依赖: pip install -r requirements.txt")
    input("\n  按回车键退出 ...")
    sys.exit(1)

port = int(os.getenv('PORT', 8000))

# 写入 PID 文件，供「一键启动.bat」精准识别并只清理本项目进程
try:
    with open(os.path.join(ROOT, 'server.pid'), 'w') as f:
        f.write(str(os.getpid()))
    _log("  [OK] 已写入 PID 文件")
except Exception as e:
    _log("  [WARN] 写入 PID 文件失败: " + str(e))

_log("  [INFO] 服务地址: http://127.0.0.1:%d" % port)
_log("  [INFO] 启动后会自动打开浏览器")
_log("=" * 50)
_log()

# 自动打开浏览器（延迟 1.5 秒，等服务真正起来）
def _open_browser():
    time.sleep(1.5)
    try:
        webbrowser.open("http://127.0.0.1:%d" % port)
    except Exception:
        pass

import threading
threading.Thread(target=_open_browser, daemon=True).start()

# 主线程直接运行服务，异常会清晰抛出
try:
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
except KeyboardInterrupt:
    print("\n  已停止服务")
except Exception as e:
    print("\n  [ERROR] 服务启动失败:", e)
    input("\n  按回车键退出 ...")
    sys.exit(1)
