#!/usr/bin/env python
"""论文智助 一键启动"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
from dotenv import load_dotenv
load_dotenv()
from server import app
import uvicorn
port = int(os.getenv('PORT', 8000))
uvicorn.run(app, host='0.0.0.0', port=port, reload=False)