import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/store_level"))

from build_keyword_theme_map_v0 import REVIEW, THEME_MAP, THEMES, build  # noqa: E402


def test_build_counts_stores_and_reviews_once_per_review():
    df = pd.DataFrame({
        "store_id": ["a", "a", "b"],
        "keywords": ["음식이 맛있어요, 친절해요", "음식이 맛있어요", "반려동물과 가기 좋아요"],
        "extra_tags": ["음식이 맛있어요", "", "새로운 키워드예요"],
    })
    out = build(df).set_index("keyword")
    assert out.loc["음식이 맛있어요", ["n_stores", "total_count"]].tolist() == [1, 2]  # 한 리뷰 안 중복은 1번
    assert out.loc["음식이 맛있어요", "themes"] == "맛"
    assert out.loc["반려동물과 가기 좋아요", "themes"] == "편의|애견동반"  # 앞이 주 테마
    assert out.loc["새로운 키워드예요", "themes"] == REVIEW


def test_theme_map_uses_known_themes_only():
    used = {t for themes, _, _ in THEME_MAP.values() for t in themes}
    assert used <= set(THEMES) | {REVIEW}
    assert all(note for themes, _, note in THEME_MAP.values() if REVIEW in themes)  # 검토필요엔 후보를 적는다
