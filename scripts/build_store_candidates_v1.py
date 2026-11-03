"""점포 후보와 접근성 판정 v1. 계산은 build_store_candidates_v0.py와 같고, 입력이 seoul_store_table_v1.csv다(점포 단계 목적·비목적지 제외가 이미 반영됨).

출력: 데이터/가공/서울캠/store_candidates_v1.csv (커밋 금지)
실행: ~/.venvs/maximus/bin/python -I scripts/build_store_candidates_v1.py (build_seoul_store_table_v1.py 먼저)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_store_candidates_v0 import main  # noqa: E402

if __name__ == "__main__":
    main("v1")
