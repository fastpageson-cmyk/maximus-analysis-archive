"""점포 의외성 v0 ↔ v1 비교(공개 CSV만 읽는다). 로컬에서 v1 산출물을 만든 뒤 돌린다.

    1 목적별 추천 수, 남음/빠짐/새로 들어옴(가게 = purpose·상호·area_name)
    2 빠진 가게 목록(v1 규칙 사전 판정 store_rules_v1_preimpact_top30.csv가 있으면 사유를 붙인다)
    3 설문 카드 덱: 방법별 카드 수, 공공 태그 없는 카드 비율(survey_cards_key_{v}.csv의 has_tag)
출력: data/processed/store_level/store_serendipity_v0_v1_compare.md
실행: python -I scripts/store_level/compare_store_serendipity_v0_v1.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

PUBLIC = Path(__file__).resolve().parents[2] / "data/processed/store_level"
PURPOSES = ["식사", "카페", "공부", "쇼핑", "여가문화"]
KEY = ["purpose", "상호", "area_name"]


def md(df: pd.DataFrame) -> str:
    cols = [str(c) for c in df.columns]
    rows = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    rows += ["| " + " | ".join("" if pd.isna(v) else str(v) for v in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join(rows)


def main() -> None:
    a = pd.read_csv(PUBLIC / "store_serendipity_top30_v0.csv")
    b = pd.read_csv(PUBLIC / "store_serendipity_top30_v1.csv")
    m = a.merge(b, on=KEY, how="outer", suffixes=("_v0", "_v1"), indicator=True)
    s = pd.DataFrame({"v0": a.purpose.value_counts(), "v1": b.purpose.value_counts(),
                      "남음": m[m._merge.eq("both")].purpose.value_counts(),
                      "빠짐": m[m._merge.eq("left_only")].purpose.value_counts(),
                      "새로 들어옴": m[m._merge.eq("right_only")].purpose.value_counts()}).reindex(PURPOSES).fillna(0).astype(int)
    out = ["# 점포 의외성 v0 ↔ v1 비교", "", "## 목적별 추천 수", "", md(s.reset_index(names="목적")), ""]

    gone = m[m._merge.eq("left_only")][KEY + ["rank_v0", "소분류명_v0", "공공태그_v0"]]
    pre = PUBLIC / "store_rules_v1_preimpact_top30.csv"
    if pre.exists():
        gone = gone.merge(pd.read_csv(pre)[["purpose", "상호", "판정"]], on=["purpose", "상호"], how="left")
        gone["판정"] = gone.판정.fillna("규칙 해당 없음(순위 밀림)").replace("유지", "규칙 해당 없음(순위 밀림)")
    out += ["## 빠진 가게", "", md(gone.sort_values(["purpose", "rank_v0"])), ""]
    new = m[m._merge.eq("right_only")][KEY + ["rank_v1", "소분류명_v1", "공공태그_v1"] + (["category_source"] if "category_source" in m else [])]
    out += ["## 새로 들어온 가게", "", md(new.sort_values(["purpose", "rank_v1"])), ""]

    rows = []
    for v in ["v0", "v1"]:
        k = pd.read_csv(PUBLIC / f"survey_cards_key_{v}.csv")
        g = k.groupby("method").agg(덱=("card_id", "size"), 공공태그없음=("has_tag", lambda x: round(1 - x.astype(bool).mean(), 3)))
        rows.append(g.add_suffix(f"_{v}"))
    cards = pd.concat(rows, axis=1).reset_index(names="method")
    out += ["## 설문 카드 덱: 공공 태그 없는 카드 비율", "", md(cards), ""]
    (PUBLIC / "store_serendipity_v0_v1_compare.md").write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
