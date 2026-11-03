"""점포 의외성 v1 검증과 설문 카드. 계산은 validate_store_serendipity_v0.py와 같고, 입력이 v1 후보다.

출력: data/processed/store_level/survey_cards_v1.csv, survey_cards_key_v1.csv, validation_summary_v1.json
실행: ~/.venvs/maximus/bin/python -I scripts/validate_store_serendipity_v1.py (build_store_serendipity_v1.py 먼저)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_store_serendipity_v0 import main  # noqa: E402

if __name__ == "__main__":
    main("v1")
