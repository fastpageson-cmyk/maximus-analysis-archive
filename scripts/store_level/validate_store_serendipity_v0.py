"""점포 단위 의외성 v0 검증과 설문 카드 (설계 문서 4.2·6.6절).

    1·2 테마 안정성·구성 타당도 = 키워드 집계가 있어야 한다. 없으면 '데이터 없음'
    3   편향 = review_evidence=low 비율을 노포/비노포, 상권 유형별로. 노포 쪽이 10%p 이상 높으면 경고
    4   기여 = 리뷰 특성 있음/없음 상위 30 자카드, 관성 상권 겹침률, ILD(서로 다른 소분류 쌍 비율), 테마 커버리지
    5   매칭 감사 = 감사 표본의 판정 칸(맞음/틀림/애매)이 있으면 정밀도 = 맞음 ÷ (맞음 + 틀림)
    6   설문 카드 = 1세트 20장: 의외성 상위 10 + 기준선 10(대표점 가까운 순 · 상권 안 무작위 비프랜차이즈 · 관성 상권 같은 규칙)
              카드의 접근 정보는 '상권 안 도보'(대표점 → 점포). 상권 자체는 동대문구 30분 안 후보다
              30세트, seed 42, 순서 무작위. 카드에는 방법을 숨기고 survey_cards_key_v0.csv에 따로 둔다
출력: data/processed/store_level/survey_cards_v0.csv, survey_cards_key_v0.csv, validation_summary_v0.json
실행: ~/.venvs/maximus/bin/python -I scripts/store_level/validate_store_serendipity_v0.py
"""

from __future__ import annotations

import json
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_store_candidates_v0 import area_reach, walk_min  # noqa: E402
from build_store_serendipity_v0 import (BASE_W, OUT, PUBLIC, PURPOSES, RARE_REASON, THEMES, add_review_terms, load,  # noqa: E402
                                        mmr, rank, reason, score)

SEED = 42
N_SETS, N_SER, N_BASE = 30, 10, 10
BASELINES = ["near_rep", "random_area", "inertia_rule"]
BIAS_WARN_PP = 10
WALK_BINS = [-1, 2, 5, 10]
WALK_LABELS = ["역·정류장 바로 앞", "도보 5분 안", "도보 5~10분"]


def ild(kinds: pd.Series) -> float:
    pairs = list(combinations(kinds, 2))
    return round(sum(a != b for a, b in pairs) / len(pairs), 3) if pairs else float("nan")


def precision(path: Path) -> dict:
    """사람 판정(판정)이 있으면 그것을, 없으면 Claude 1차 판정(판정_claude)을 쓴다. 애매를 틀림으로 본 보수적 정밀도도 함께."""
    if not path.exists():
        return {"status": "파일 없음"}
    a = pd.read_csv(path)
    for col, status in [("판정", "사람 검수"), ("판정_claude", "Claude 1차 판정(사람 검수 전)")]:
        j = a.get(col, pd.Series(dtype=str)).fillna("").astype(str).str.strip()
        done = j.isin(["맞음", "틀림", "애매"])
        if done.any():
            right, wrong = int(j.eq("맞음").sum()), int(j.eq("틀림").sum())
            return {"status": status, "n_judged": int(done.sum()), "counts": j[done].value_counts().to_dict(),
                    "precision": round(right / (right + wrong), 3) if right + wrong else None,
                    "precision_conservative": round(right / int(done.sum()), 3)}
    return {"status": "검수 필요", "n": len(a)}


def baselines(c: pd.DataFrame, vec_cols: list[str], picked_areas: pd.DataFrame, tag: str = "v0") -> pd.DataFrame:
    """기준선 3종. 의외성 추천과 같은 상권·목적(①②), 관성 상권(③)에서 상권마다 3곳."""
    rng = np.random.default_rng(SEED)
    pool = c[c.mmr_rank.le(10) & c.reach_flag.ne("제외") & ~c.franchise].merge(picked_areas, on=["purpose", "area_code"])
    reach = area_reach()[["area_code", "rep_lat", "rep_lon"]]
    pool = pool.merge(reach, on="area_code")
    pool["d_rep"] = walk_min(pool.rep_lat, pool.rep_lon, pool.lat, pool.lon)
    near = pool.sort_values("d_rep").groupby(["purpose", "area_code"]).head(3).assign(method="near_rep")
    rand = pool.assign(r=rng.random(len(pool))).sort_values("r").groupby(["purpose", "area_code"]).head(3).assign(method="random_area")

    ref = pd.read_csv(OUT / f"store_candidates_{tag}.csv", dtype={"store_id": str, "area_code": str, "소분류코드": str}, low_memory=False)
    ref = ref[ref.group.eq("inertia_ref") & ref.reach_flag.ne("제외") & ~ref.franchise.astype(bool) & ref.목적.eq(ref.purpose)].copy()
    for col in ["nopo", "tenure10", "goodprice", "old_cafe"]:
        ref[col] = ref[col].astype(bool)
    ref = ref.merge(c[["store_id", "age_pct"]].drop_duplicates("store_id"), on="store_id", how="left")
    ref = ref.assign(age_pct=ref.age_pct.fillna(0.5), fit=0.5, u_content=0.5, u_local=0.5, **{v: 0.0 for v in vec_cols})
    ref = score(ref, BASE_W)
    inertia = pd.concat([mmr(g, vec_cols) for _, g in ref.groupby(["purpose", "area_code"])], ignore_index=True).assign(method="inertia_rule")
    return pd.concat([near, rand, inertia], ignore_index=True)


def cards(ser: pd.DataFrame, base: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    deck = pd.concat([ser.assign(method="serendipity"), base], ignore_index=True)
    deck = deck.drop_duplicates(["store_id", "method"]).reset_index(drop=True)
    deck["card_id"] = [f"C{i:04d}" for i in range(len(deck))]
    deck["상권 안 도보"] = pd.cut(deck.walk_from_rep, WALK_BINS, labels=WALK_LABELS).astype(str)
    deck["reason"] = [reason(r, {t: r[f"t_{t}"] for t in THEMES}) for _, r in deck.iterrows()]
    rng = np.random.default_rng(SEED)
    sets = []
    ser_ids = deck.index[deck.method.eq("serendipity")].to_numpy()
    for s in range(1, N_SETS + 1):
        pick = list(rng.choice(ser_ids, min(N_SER, len(ser_ids)), replace=False))
        used = set(deck.loc[pick, "store_id"])
        quota = rng.multinomial(N_BASE, [1 / 3] * 3)  # 기준선 3종을 섞어 10장
        for m, q in zip(BASELINES, quota):
            ids = deck.index[deck.method.eq(m) & ~deck.store_id.isin(used)].to_numpy()
            chosen = list(rng.choice(ids, min(q, len(ids)), replace=False))
            used |= set(deck.loc[chosen, "store_id"])
            pick += chosen
        order = rng.permutation(len(pick))
        sets += [{"set_id": s, "order": o + 1, "card_id": deck.at[pick[i], "card_id"]} for o, i in enumerate(order)]
    sets = pd.DataFrame(sets).merge(deck[["card_id", "상호", "소분류명", "area_name", "상권 안 도보", "reason"]], on="card_id")
    # 공공 태그가 이유 문장에 있는지(방법마다 비율이 달라 분석 때 공변량으로 넣는다)
    deck["has_tag"] = deck.nopo | deck.tenure10 | deck.goodprice | deck.rarity.ge(RARE_REASON)
    key = deck[["card_id", "method", "purpose", "has_tag"]]
    return sets.sort_values(["set_id", "order"]), key


def main(tag: str = "v0") -> None:
    """tag = v0 / v1: 입력·출력 파일 이름의 버전. 매칭 감사 표본은 v0 것을 그대로 쓴다(매칭 규칙은 같다)."""
    c, vec_cols = load(tag)
    c = add_review_terms(c, vec_cols, tag)
    top = rank(c, BASE_W, vec_cols)
    summary: dict = {}
    has_reviews = c.review_evidence.eq("ok").any()
    summary["1_theme_stability"] = "데이터 없음(키워드 집계 미수집)" if not has_reviews else "TODO"
    summary["2_construct_validity"] = "데이터 없음(키워드 집계 미수집)" if not has_reviews else "TODO"

    low = c.review_evidence.eq("low")
    by_nopo = low.groupby(c.nopo).mean().round(3).rename({True: "노포", False: "비노포"}).to_dict()
    by_type = low.groupby(c.area_type_name).mean().round(3).to_dict()
    gap = (by_nopo.get("노포", 0) - by_nopo.get("비노포", 0)) * 100
    summary["3_bias"] = {"low_by_nopo": by_nopo, "low_by_area_type": by_type, "warn": bool(gap >= BIAS_WARN_PP)}

    inertia = pd.read_csv(PUBLIC.parent / "serendipity_ranking/inertia_baselines_top10.csv", dtype={"area_code": str})
    inertia_set = set(zip(inertia.purpose, inertia.area_code))
    contrib = {}
    for p in PURPOSES:
        t = top[top.purpose.eq(p)]
        contrib[p] = {"n": len(t), "jaccard_with_vs_without_reviews": 1.0 if not has_reviews else None,
                      "inertia_area_overlap": round(np.mean([(p, a) in inertia_set for a in t.area_code]), 3) if len(t) else None,
                      "ild_subtype": ild(t.소분류명), "theme_coverage": "데이터 없음" if not has_reviews else None}
    summary["4_contribution"] = contrib

    summary["5_match_audit"] = {"license": precision(PUBLIC / "match_audit_sample_v0.csv"),
                                "naver": precision(PUBLIC / "naver_match_audit_sample_v0.csv")}

    picked_areas = top[["purpose", "area_code"]].drop_duplicates()
    base = baselines(c, vec_cols, picked_areas, tag)
    sets, key = cards(top, base)
    sets.to_csv(PUBLIC / f"survey_cards_{tag}.csv", index=False, encoding="utf-8-sig")
    key.to_csv(PUBLIC / f"survey_cards_key_{tag}.csv", index=False, encoding="utf-8-sig")
    summary["6_survey"] = {"sets": int(sets.set_id.nunique()), "cards_per_set": sets.groupby("set_id").size().describe()[["min", "max"]].to_dict(),
                           "deck": key.method.value_counts().to_dict(),
                           "has_tag_by_method": key.groupby("method").has_tag.mean().round(2).to_dict(),
                           "baseline_mix_per_set": sets.merge(key, on="card_id").groupby(["set_id", "method"]).size().unstack(fill_value=0).mean().round(2).to_dict()}
    (PUBLIC / f"validation_summary_{tag}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
