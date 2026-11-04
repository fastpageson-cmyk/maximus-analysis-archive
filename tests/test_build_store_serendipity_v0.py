import numpy as np
import pandas as pd

from scripts.store_level.build_store_serendipity_v0 import BASE_W, THEMES, rank, shrunk_lift

VEC = [f"t_{t}" for t in THEMES]


def frame(n, **over):
    base = dict(purpose="식사", area_code="A", mmr_rank=1, reach_flag="안정", franchise=False, age_pct=0.5, goodprice=False,
                fit=0.5, nopo=False, tenure10=False, rarity=0.5, u_content=0.5, u_local=0.5, serendipity_score=1.0,
                u_novelty_store=0.5)
    d = pd.DataFrame([{**base, "store_id": f"S{i}", "소분류명": f"업종{i}"} for i in range(n)])
    for k, v in over.items():
        d[k] = v
    d[VEC] = 0.0
    return d


def test_shrunk_lift_pulls_small_samples_to_group_mean():
    mu = np.array([0.2])
    # 리뷰 0건이면 업종 평균 그대로 → lift 0
    assert np.isclose(shrunk_lift(np.array([0.0]), 0, mu), 0.0)
    # 같은 관측 비율 0.6이라도 n이 클수록 lift가 커진다
    small, big = shrunk_lift(np.array([3.0]), 5, mu), shrunk_lift(np.array([300.0]), 500, mu)
    assert 0 < small[0] < big[0] < np.log(0.6 / 0.2)
    assert np.isclose(small[0], np.log(((3 + 20 * 0.2) / 25) / 0.2))


def test_low_evidence_is_kept_with_neutral_terms():
    out = rank(frame(2), BASE_W, VEC)
    assert len(out) == 2  # 근거 부족이어도 빠지지 않는다


def test_at_most_three_per_area_and_one_per_subtype():
    d = frame(6)
    d.loc[[0, 1], "소분류명"] = "같은업종"
    d.loc[0, "rarity"] = 0.9
    out = rank(d, BASE_W, VEC)
    assert len(out) == 3 and out.소분류명.value_counts().max() == 1 and "S0" in set(out.store_id)


def test_franchise_and_excluded_reach_are_dropped():
    d = frame(3)
    d.loc[0, "franchise"] = True
    d.loc[1, "reach_flag"] = "제외"
    assert list(rank(d, BASE_W, VEC).store_id) == ["S2"]
