import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "build_serendipity_ranking.py"
SPEC = importlib.util.spec_from_file_location("serendipity", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules["serendipity"] = MODULE  # dataclass가 모듈을 찾을 수 있게
SPEC.loader.exec_module(MODULE)

PURPOSES = ["식사", "공부"]


def synthetic_inputs(n: int = 120, seed: int = 7):
    """후보 n곳 합성 자료. 공부는 매출 없음(공급 점수 대체 경로)."""
    rng = np.random.default_rng(seed)
    codes = [str(3000000 + i) for i in range(n)]
    lat = 37.58 + rng.normal(0, 0.03, n)
    lon = 127.04 + rng.normal(0, 0.04, n)
    stores = rng.integers(10, 2000, n)
    area = pd.DataFrame({
        "area_code": codes,
        "area_name": [f"상권{i}" for i in range(n)],
        "area_type_name": rng.choice(MODULE.AREA_TYPES, n, p=[.6, .2, .15, .05]),
        "primary_district_name": rng.choice(["동대문구", "성북구", "중랑구", "종로구"], n),
        "mean_period_ratio": rng.uniform(.25, 1, n),
        "minimum_period_ratio": rng.uniform(.25, 1, n),
        "lat": lat, "lon": lon,
        "dist_km": MODULE.haversine_km(37.58, 127.04, lat, lon),
        "log_store_total": np.log1p(stores),
        "log_area_m2": rng.normal(11, 1, n),
        "industry_entropy": rng.uniform(1, 3.5, n),
        "share_식사": rng.uniform(0, .5, n), "share_카페": rng.uniform(0, .2, n),
        "share_쇼핑": rng.uniform(0, .5, n), "share_여가문화": rng.uniform(0, .1, n),
        "share_공부": rng.uniform(0, .02, n),
        "lagged_total_sales": stores * rng.lognormal(16, .5, n),
    })
    area["observed_inflow"] = stores * rng.lognormal(4, .6, n) * area["mean_period_ratio"]
    area["log_observed"] = np.log1p(area["observed_inflow"])
    rows = []
    for p in PURPOSES:
        sales = 0 if p == "공부" else stores * rng.lognormal(14, .8, n)
        rows.append(pd.DataFrame({
            "area_code": codes, "purpose": p,
            "purpose_store_count": (stores * rng.uniform(.01, .4, n)).round(),
            "purpose_store_share": rng.uniform(0, .4, n),
            "purpose_sales_amount": sales,
            "lagged_purpose_sales": 0 if p == "공부" else sales * rng.uniform(.8, 1.2, n),
            "purpose_supply_score": rng.uniform(0, 100, n),
            "path_v0_score": rng.uniform(0, 100, n),
        }))
    return area, pd.concat(rows, ignore_index=True)


@pytest.fixture(scope="module")
def built():
    area, purpose = synthetic_inputs()
    cfg = MODULE.Config(top_k=10, r_floor=0.6)
    full, base = MODULE.build_serendipity(area, purpose, cfg)
    return cfg, full, base


# --- 점수 단조성 -----------------------------------------------------------

def test_score_monotone_in_relevance_and_unexpectedness():
    grid = np.linspace(0.6, 1.0, 9)
    for u in [0.1, 0.5, 0.9]:
        s = MODULE.combine_scores(pd.Series(grid), pd.Series(u, index=range(9)), 0.6)
        assert s.is_monotonic_increasing and s.diff().dropna().gt(0).all()
    for r in [0.6, 0.8, 1.0]:
        s = MODULE.combine_scores(pd.Series(r, index=range(9)), pd.Series(grid), 0.6)
        assert s.is_monotonic_increasing


def test_unexpectedness_monotone_in_each_component(built):
    cfg, full, _ = built
    g = full[full["purpose"] == "식사"]
    recomputed = (cfg.w_resid * g["u_resid"] + cfg.w_novelty * g["u_novelty"]
                  + cfg.w_cat * g["u_cat"] + cfg.w_spatial * g["u_spatial"])
    assert np.allclose(recomputed, g["unexpectedness"])
    assert min(cfg.w_resid, cfg.w_novelty, cfg.w_cat, cfg.w_spatial) >= 0


def test_lower_observed_inflow_raises_u_resid():
    area, _ = synthetic_inputs()
    cfg = MODULE.Config()
    a = MODULE.add_inflow_residual(area, cfg)
    target = (a["u_resid"] - 0.5).abs().idxmin()  # 중간 백분위 상권(천장 효과 회피)
    lowered = area.copy()
    lowered.loc[target, "log_observed"] -= 3.0
    b = MODULE.add_inflow_residual(lowered, cfg)
    assert b.loc[target, "u_resid"] > a.loc[target, "u_resid"]
    assert b.loc[target, "inflow_residual_z"] < a.loc[target, "inflow_residual_z"]


def test_score_order_matches_serendipity_score(built):
    _, full, _ = built
    for _, g in full.groupby("purpose"):
        e = g[g["eligible"]].sort_values("score_rank")
        assert e["serendipity_score"].is_monotonic_decreasing


# --- R 하한 컷 -------------------------------------------------------------

def test_relevance_floor_excludes_low_relevance():
    s = MODULE.combine_scores(pd.Series([0.1, 0.59, 0.6, 0.9]), pd.Series([1.0, 1.0, 0.2, 0.2]), 0.6)
    assert s.isna().tolist() == [True, True, False, False]


def test_floor_respected_in_outputs(built):
    cfg, full, _ = built
    assert (full.loc[full["eligible"], "relevance"] >= cfg.r_floor).all()
    picked = full[full["mmr_rank"].notna()]
    assert len(picked) > 0
    assert (picked["relevance"] >= cfg.r_floor).all()
    assert full.loc[full["relevance"] < cfg.r_floor, "serendipity_score"].isna().all()


def test_relevance_in_unit_interval_and_study_uses_supply_fallback(built):
    _, full, _ = built
    assert full["relevance"].between(0, 1).all()
    study = full[full["purpose"] == "공부"]["relevance_source"].unique().tolist()
    assert study == ["PATH-v0 공급 점수(매출 원천 없음)"]


# --- 관성 Top-K 겹침률 ----------------------------------------------------

def test_overlap_at_k():
    assert MODULE.overlap_at_k(list("abcde"), list("cdefg"), 5) == pytest.approx(0.6)
    assert MODULE.overlap_at_k(list("abc"), list("xyz"), 3) == 0.0


def test_inertia_members_get_zero_category_and_spatial_distance(built):
    _, full, _ = built
    members = full[full["in_inertia_topk"]]
    assert np.allclose(members["spatial_distance_km"], 0)
    assert np.allclose(members["cat_distance"], 0, atol=1e-9)


def test_serendipity_overlap_with_inertia_is_lower_than_baselines(built):
    cfg, full, base = built
    m = MODULE.beyond_accuracy(full, base, cfg)
    per = m[m["purpose"] != "_전체"].groupby("method")["overlap_inertia_union"].mean()
    assert per["serendipity"] < 0.3
    for b in MODULE.BASELINES:
        assert per[b] == pytest.approx(1.0)


def test_baselines_share_candidate_set(built):
    _, full, base = built
    for p, g in base.groupby("purpose"):
        assert set(g["area_code"]) <= set(full.loc[full["purpose"] == p, "area_code"])


# --- MMR, 보조 지표 --------------------------------------------------------

def test_mmr_lambda_one_equals_score_order(built):
    cfg, full, _ = built
    g = full[full["purpose"] == "식사"].reset_index(drop=True)
    order = MODULE.mmr_rerank(g, "serendipity_score", 10, 1.0, cfg.spatial_scale_km)
    expected = g["serendipity_score"].sort_values(ascending=False).index[:10].tolist()
    assert order == expected


def test_mmr_returns_unique_eligible_items(built):
    cfg, full, _ = built
    g = full[full["purpose"] == "식사"].reset_index(drop=True)
    order = MODULE.mmr_rerank(g, "serendipity_score", 20, 0.5, cfg.spatial_scale_km)
    assert len(order) == len(set(order)) == 20
    assert g.loc[order, "eligible"].all()


def test_gini_bounds():
    assert MODULE.gini([1, 1, 1, 1]) == pytest.approx(0.0)
    assert MODULE.gini([0, 0, 0, 10]) == pytest.approx(0.75)
