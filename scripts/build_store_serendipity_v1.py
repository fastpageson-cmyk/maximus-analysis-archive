"""점포 의외성 점수와 목적별 추천 30곳 v1. 계산은 build_store_serendipity_v0.py와 같고, 입력이 v1 후보·점포 테이블이다(희소도는 목적지형 소분류만, 업종은 보정값).

출력: 데이터/가공/서울캠/store_serendipity_v1.csv (커밋 금지), data/processed/store_level/store_serendipity_top30_v1.csv, store_serendipity_sensitivity_v1.csv
실행: ~/.venvs/maximus/bin/python -I scripts/build_store_serendipity_v1.py (build_store_candidates_v1.py 먼저)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_store_serendipity_v0 import main  # noqa: E402

if __name__ == "__main__":
    main("v1")
