#!/usr/bin/env python
"""
API 서버 실행 스크립트
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from api.server import main

if __name__ == "__main__":
    main()