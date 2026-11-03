"""점포 단위 의외성 점수와 목적별 추천 30곳 v0 (설계 문서 3.3·6.4~6.5절).

    성격 벡터 = 네이버 키워드 집계(naver_keyword_counts_v0.csv)와 테마 사전(keyword_theme_map_v0.csv)이 둘 다 있을 때만 만든다
               p̃ = (c + m·μ_gk) / (n + m), ℓ = log(p̃ / μ_gk), t_θ = Σ_{k∈θ} w_gk·ℓ_k. n < 20이거나 연결 실패면 review_evidence=low
               2026-11-03: 키워드 집계는 캡차 토큰 없이 받을 수 없어(429) 파일이 없다 → 모든 점포가 low, 리뷰 항은 0.5
    관련성   r_store = 0.4·pct(영업연수 | 소분류) + 0.2·goodprice + 0.4·fit  (오래가게 지정 원천은 아직 없음, 인허가 없는 점포의 영업연수는 0.5)
    의외성   u_store = 0.3·rarity + 0.2·(노포 1, 10년+ 0.5) + 0.3·u_content + 0.2·u_local
    순위     s_store = r_store × u_store → 상권 안 MMR(λ=0.7, 벡터 코사인, 같은 소분류 1곳) 3곳
             S = serendipity_score × s_store, 목적별 30곳, 상권당 최대 3곳, reach_flag=제외는 MMR 전에 뺀다
출력: 데이터/가공/서울캠/store_serendipity_v0.csv (전체 열, 커밋 금지)
      data/processed/store_level/store_serendipity_top30_v0.csv, store_serendipity_sensitivity_v0.csv
실행: ~/.venvs/maximus/bin/python -I scripts/build_store_serendipity_v0.py
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ["MAXIMUS_WORKSPACE"]) if "MAXIMUS_WORKSPACE" in os.environ else next((p for p in REPO.parents if (p / "데이터").is_dir()), REPO.parent)
OUT = ROOT / "데이터/가공/서울캠"
PUBLIC = REPO / "data/processed/store_level"
RANKING = REPO / "data/processed/serendipity_ranking/serendipity_ranking_latest.csv"
KEYWORDS = OUT / "naver_keyword_counts_v0.csv"
THEME_MAP = PUBLIC / "keyword_theme_map_v0.csv"
YEAR = 2026
PURPOSES = ["식사", "카페", "공부", "쇼핑", "여가문화"]
THEMES = ["맛", "가성비·양", "조용·아늑", "감성·인테리어·뷰", "오래 머물기·공부", "혼자", "대화·모임", "특별함", "서비스·청결", "편의"]
PURPOSE_THEMES = {"식사": {"맛", "가성비·양", "혼자", "특별함"}, "카페": {"맛", "조용·아늑", "감성·인테리어·뷰", "대화·모임"},
                  "공부": {"조용·아늑", "오래 머물기·공부"}}
M_PRIOR, MIN_N, MIN_GROUP = 20, 20, 10
LIFT_REASON = 0.4
LAMBDA, PER_AREA, TOP_N = 0.7, 3, 30
RARE_REASON = 0.8
BASE_W = {"r_age": 0.4, "r_good": 0.2, "r_fit": 0.4, "u_rare": 0.3, "u_old": 0.2, "u_content": 0.3, "u_local": 0.2}


def shrunk_lift(c: np.ndarray, n: float, mu: np.ndarray, m: float = M_PRIOR) -> np.ndarray:
    """경험적 베이즈 축소 뒤 업종 평균 대비 log 배율: log(((c + m·μ)/(n + m)) / μ)."""
    return np.log(((c + m * mu) / (n + m)) / mu)


def theme_vectors(kw: pd.DataFrame, stores: pd.DataFrame, theme_map: pd.DataFrame, m: float = M_PRIOR) -> pd.DataFrame:
    """가게 × 테마 점수. kw: store_id, keyword, count, n_participants / stores: store_id, 소분류명, 중분류(없으면 소분류).
    μ_gk = 같은 소분류 평균 비율(가게 10곳 미만이면 중분류), w_gk = 소분류 안 평균 비중을 테마 안에서 합 1로."""
    kw = kw.merge(stores[["store_id", "소분류명", "group_up"]], on="store_id").merge(theme_map[["keyword", "theme"]], on="keyword")
    kw = kw[kw.theme.isin(THEMES)]
    n_store = kw.groupby("소분류명").store_id.nunique()
    kw["g"] = np.where(kw.소분류명.map(n_store).fillna(0) >= MIN_GROUP, kw.소분류명, kw.group_up)
    kw["p"] = kw["count"] / kw.n_participants
    stores_in_g = kw.groupby("g").store_id.nunique()
    mu = (kw.groupby(["g", "keyword"]).p.sum() / kw.groupby(["g", "keyword"]).g.first().map(stores_in_g)).rename("mu")
    kw = kw.join(mu, on=["g", "keyword"])
    kw["lift"] = shrunk_lift(kw["count"].to_numpy(float), kw.n_participants.to_numpy(float), kw.mu.to_numpy(float), m)
    kw["w"] = kw.mu / kw.groupby(["g", "theme"]).mu.transform("sum")
    t = (kw.w * kw.lift).groupby([kw.store_id, kw.theme]).sum().unstack(fill_value=0.0)
    return t.reindex(columns=THEMES, fill_value=0.0)


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return float(a @ b / (na * nb)) if na and nb else 0.0


def mmr(group: pd.DataFrame, vec_cols: list[str], k: int = PER_AREA, lam: float = LAMBDA) -> pd.DataFrame:
    """상권 안 MMR: λ·s/max(s) − (1−λ)·max 코사인, 같은 소분류는 한 곳만."""
    g = group.sort_values("s_store", ascending=False)
    top = g.s_store.max() or 1.0
    vecs, picked, kinds = g[vec_cols].to_numpy(float), [], set()
    for _ in range(k):
        best, best_val = None, -np.inf
        for i, (idx, row) in enumerate(g.iterrows()):
            if idx in picked or row.소분류명 in kinds:
                continue
            sim = max((cosine(vecs[i], vecs[g.index.get_loc(j)]) for j in picked), default=0.0)
            val = lam * row.s_store / top - (1 - lam) * sim
            if val > best_val:
                best, best_val = idx, val
        if best is None:
            break
        picked.append(best)
        kinds.add(g.at[best, "소분류명"])
    return g.loc[picked]


def reason(row: pd.Series, lifts: dict[str, float]) -> str:
    parts = [f"같은 업종보다 '{t}' {np.exp(v):.1f}배" for t, v in sorted(lifts.items(), key=lambda x: -x[1])[:2] if v >= LIFT_REASON]
    if row.nopo:
        parts.append(f"{int(row.license_year)}년 인허가 노포")
    elif row.tenure10:
        parts.append(f"{int(row.license_year)}년부터 10년 넘게 영업")
    if row.goodprice:
        parts.append("착한가격업소")
    if row.rarity >= RARE_REASON:
        parts.append(f"이 상권에 드문 {row.소분류명}")
    return " · ".join(parts) or f"{row.area_name}의 {row.소분류명}"  # 태그가 없으면 중립 문구(설문 카드에서 출처가 드러나지 않게)


def score(c: pd.DataFrame, w: dict[str, float]) -> pd.DataFrame:
    c = c.copy()
    c["r_store"] = w["r_age"] * c.age_pct + w["r_good"] * c.goodprice.astype(float) + w["r_fit"] * c.fit
    old = np.where(c.nopo, 1.0, np.where(c.tenure10, 0.5, 0.0))
    c["u_store"] = w["u_rare"] * c.rarity + w["u_old"] * old + w["u_content"] * c.u_content + w["u_local"] * c.u_local
    c["s_store"] = c.r_store * c.u_store
    return c


def rank(c: pd.DataFrame, w: dict[str, float], vec_cols: list[str], k: int = 10, novelty_w: float = 0.0) -> pd.DataFrame:
    c = score(c[c.mmr_rank.le(k) & c.reach_flag.ne("제외") & ~c.franchise], w)
    if novelty_w:
        c["s_store"] = (1 - novelty_w) * c.s_store + novelty_w * c.u_novelty_store
    picked = pd.concat([mmr(g, vec_cols) for _, g in c.groupby(["purpose", "area_code"])], ignore_index=True)
    picked["S"] = picked.serendipity_score * picked.s_store
    picked = picked.sort_values(["purpose", "S"], ascending=[True, False])
    picked["rank"] = picked.groupby("purpose").cumcount() + 1
    return picked[picked["rank"].le(TOP_N)]


def load() -> tuple[pd.DataFrame, list[str]]:
    c = pd.read_csv(OUT / "store_candidates_v0.csv", dtype={"store_id": str, "area_code": str, "소분류코드": str}, low_memory=False)
    c = c[c.group.eq("candidate")].copy()
    for col in ["nopo", "tenure10", "goodprice", "franchise", "old_cafe"]:
        c[col] = c[col].astype(bool)
    stores = pd.read_csv(OUT / "seoul_store_table_v0.csv", dtype={"store_id": str, "소분류코드": str}, usecols=["store_id", "소분류명", "소분류코드", "license_year"])
    age = (YEAR - stores.license_year)
    stores["age_pct"] = age.groupby(stores.소분류명).rank(pct=True).fillna(0.5)
    c = c.merge(stores[["store_id", "age_pct"]], on="store_id", how="left")
    rank_cols = ["purpose", "area_code", "serendipity_score", "area_type_name"]
    c = c.merge(pd.read_csv(RANKING, dtype={"area_code": str})[rank_cols], on=["purpose", "area_code"], how="left")

    vec_cols = [f"t_{t}" for t in THEMES]
    c[vec_cols] = 0.0
    c["review_evidence"] = "low"
    c["n_participants"] = np.nan
    c["u_novelty_store"] = 0.5
    if KEYWORDS.exists() and THEME_MAP.exists():
        kw = pd.read_csv(KEYWORDS, dtype={"store_id": str})
        info = stores[["store_id", "소분류명"]].assign(group_up=stores.소분류코드.str[:4].fillna(stores.소분류명))
        vec = theme_vectors(kw, info, pd.read_csv(THEME_MAP))
        n = kw.groupby("store_id").n_participants.first()
        ok = c.store_id.map(n).fillna(0).ge(MIN_N) & c.store_id.isin(vec.index)
        c.loc[ok, vec_cols] = vec.loc[c.loc[ok, "store_id"]].to_numpy()
        c.loc[ok, "review_evidence"] = "ok"
        c["n_participants"] = c.store_id.map(n)
        visits = np.log1p(kw.groupby("store_id").n_visitor_reviews.first())
        c["u_novelty_store"] = (1 - c.store_id.map(visits).groupby(c.소분류명).rank(pct=True)).fillna(0.5)
    return c, vec_cols


def add_review_terms(c: pd.DataFrame, vec_cols: list[str]) -> pd.DataFrame:
    ok = c.review_evidence.eq("ok")
    a = {p: np.array([t in PURPOSE_THEMES.get(p, set()) for t in THEMES], float) for p in PURPOSES}
    fit = pd.Series([c.loc[i, vec_cols].to_numpy(float) @ a[p] for i, p in zip(c.index, c.purpose)], index=c.index)
    c["fit"] = np.where(ok, fit.where(ok).groupby(c.purpose).rank(pct=True), 0.5)
    c["u_content"], c["u_local"] = 0.5, 0.5
    if ok.any():
        # 관성 상권 평균 벡터·상권 candidate 평균 벡터는 리뷰가 있는 점포로만 만든다
        ref = pd.read_csv(OUT / "store_candidates_v0.csv", dtype={"store_id": str, "area_code": str}, low_memory=False)
        ref = ref[ref.group.eq("inertia_ref")].merge(c[["store_id"] + vec_cols].drop_duplicates("store_id"), on="store_id")
        inertia = ref.groupby("area_code")[vec_cols].mean().to_numpy(float)
        v = c[vec_cols].to_numpy(float)
        c.loc[ok, "u_content"] = [1 - max((cosine(x, y) for y in inertia), default=0.0) for x in v[ok.to_numpy()]]
        area_mean = c[ok].groupby(["purpose", "area_code"])[vec_cols].transform("mean")
        dist = pd.Series(np.linalg.norm(c.loc[ok, vec_cols].to_numpy(float) - area_mean.to_numpy(float), axis=1), index=c.index[ok])
        c.loc[ok, "u_local"] = dist.groupby([c.loc[ok, "purpose"], c.loc[ok, "area_code"]]).rank(pct=True)
    return c


def main() -> None:
    c, vec_cols = load()
    c = add_review_terms(c, vec_cols)
    base = rank(c, BASE_W, vec_cols)
    full = score(c, BASE_W).merge(base[["purpose", "store_id", "S", "rank"]], on=["purpose", "store_id"], how="left")
    full["reason"] = [reason(r, {t: r[f"t_{t}"] for t in THEMES}) for _, r in full.iterrows()]
    full.to_csv(OUT / "store_serendipity_v0.csv", index=False, encoding="utf-8-sig")

    top = base.merge(full[["purpose", "store_id", "reason"]], on=["purpose", "store_id"])
    top["테마태그"] = [" · ".join(t for t in THEMES if r[f"t_{t}"] >= LIFT_REASON) for _, r in top.iterrows()]
    top["공공태그"] = [" · ".join(n for n, f in [("노포", r.nopo), ("10년+", r.tenure10), ("오래된 카페", r.old_cafe),
                                              ("착한가격", r.goodprice), ("희소 업종", r.rarity >= RARE_REASON)] if f) for _, r in top.iterrows()]
    cols = ["purpose", "rank", "상호", "소분류명", "area_name", "테마태그", "공공태그", "reach_flag", "review_evidence", "reason"]
    top.sort_values(["purpose", "rank"])[cols].to_csv(PUBLIC / "store_serendipity_top30_v0.csv", index=False, encoding="utf-8-sig")

    sens = sensitivity(c, vec_cols, base)
    sens.to_csv(PUBLIC / "store_serendipity_sensitivity_v0.csv", index=False, encoding="utf-8-sig")
    report(c, base, sens)


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a | b else 1.0


def sensitivity(c: pd.DataFrame, vec_cols: list[str], base: pd.DataFrame) -> pd.DataFrame:
    variants = {"K=20": dict(k=20)}
    for key in BASE_W:
        for d in (-0.1, 0.1):
            variants[f"{key} {d:+.1f}"] = dict(w={**BASE_W, key: max(BASE_W[key] + d, 0.0)})
    variants["인기 감점 0.1"] = dict(novelty_w=0.1)
    rows = []
    for name, kw in variants.items():
        alt = rank(c, kw.get("w", BASE_W), vec_cols, k=kw.get("k", 10), novelty_w=kw.get("novelty_w", 0.0))
        for p in PURPOSES:
            a, b = set(base[base.purpose.eq(p)].store_id), set(alt[alt.purpose.eq(p)].store_id)
            rows.append({"variant": name, "purpose": p, "n_base": len(a), "n_alt": len(b), "jaccard_top30": round(jaccard(a, b), 3)})
    note = "리뷰 데이터 없음: m·인기 감점 민감도는 기본판과 같다" if c.review_evidence.eq("low").all() else ""
    return pd.DataFrame(rows).assign(note=note)


def report(c: pd.DataFrame, base: pd.DataFrame, sens: pd.DataFrame) -> None:
    print("review_evidence=low 비율", round(c.review_evidence.eq("low").mean(), 3))
    print("목적별 추천 수", base.purpose.value_counts().reindex(PURPOSES).to_dict(), "상권 수", base.groupby("purpose").area_code.nunique().to_dict())
    for p in PURPOSES:
        print(f"\n[{p}] 상위 10")
        print(base[base.purpose.eq(p)].head(10)[["rank", "상호", "소분류명", "area_name", "reach_flag", "S"]].round(3).to_string(index=False))
    print("\n민감도 자카드(목적별)\n", sens.pivot(index="variant", columns="purpose", values="jaccard_top30")[PURPOSES].to_string())


if __name__ == "__main__":
    main()
