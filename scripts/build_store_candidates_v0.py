"""의외성 상위 상권 안 점포 후보와 점포 접근성 판정 v0.

    상권   = SERP-v0 serendipity_ranking_latest.csv 목적별 MMR 상위 K(기본 10, 민감도 20·eligible 전체)
    gate   = 점포 목적 = 해당 목적 ∧ 비프랜차이즈 (영업 중은 점포 테이블 v0에서 이미 거름)
    출발점 = 동대문구(SERP-v0·PATH-v0와 같음, 2026-11-03 팀 결정). 상권은 이미 동대문구 출발지 25% 이상이 30분 안에 닿는 곳이다
             점포 판정은 상권 대표점 → 점포 도보 시간(walk_from_rep): ≤5분 안정, 5~10분 경계, >10분 제외 → reach_flag
    참고   = 서울캠 출발 t_store_seoulcampus (seoulcampus_flag ≤25 안정, 25~30 경계, >30 제외)
             t_store = t_area − walk(하차점→상권 대표점) + walk(하차점→점포), walk = 직선 × 1.3 ÷ 시속 4km
             t_area: 서울캠 ODsay 캐시(측정)가 있으면 최단 totalTime, 없으면 캐시로 맞춘 직선거리 회귀(추정). ODsay는 새로 부르지 않는다
             하차점: 캐시 경로의 마지막 탑승 구간 끝 좌표, 추정 상권은 대표점에서 가장 가까운 버스 정류소·지하철역
             직선 1km 안 상권은 걷는 쪽이 더 빠르면 걸어간다(하차점 = 캠퍼스, build_seoulcampus_recommendations_v1.py와 같은 규칙)
             wait_risk는 seoulcampus_areas_reach_v1.csv 값
    관성   = inertia_baselines_top10.csv 상권마다 식사·카페 점포 최대 50곳 무작위(seed 42, 상권마다 한 번 뽑아 목적끼리 같이 씀)
출력: 데이터/가공/서울캠/store_candidates_v0.csv (커밋 금지)
실행: ~/.venvs/maximus/bin/python -I scripts/build_store_candidates_v0.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ["MAXIMUS_WORKSPACE"]) if "MAXIMUS_WORKSPACE" in os.environ else next((p for p in REPO.parents if (p / "데이터").is_dir()), REPO.parent)
DATA = REPO / "data/processed"
OUT = ROOT / "데이터/가공/서울캠"
STORES = OUT / "seoul_store_table_v0.csv"
CACHE = ROOT / "데이터/캐시/서울캠_odsay"
CAMPUS = (37.59754, 127.05785)  # build_seoulcampus_recommendations_v1.py와 같은 출발점
PURPOSES = ["식사", "카페", "공부", "쇼핑", "여가문화"]
K, K_SENS = 10, 20
DETOUR, WALK_KMH = 1.3, 4.0
WALK_COMPARE_KM = 1.0
STABLE_MIN, REACH_MIN = 25, 30      # 서울캠 출발(참고)
REP_STABLE_MIN, REP_MAX_MIN = 5, 10  # 상권 대표점 → 점포 도보(판정)
INERTIA_PURPOSES = {"식사", "카페"}
INERTIA_PER_AREA = 50
SEED = 42


def walk_min(lat1, lon1, lat2, lon2) -> np.ndarray:
    """직선거리(하버사인) × 1.3 ÷ 시속 4km, 분."""
    p = np.radians
    a = np.sin(p(np.asarray(lat2) - lat1) / 2) ** 2 + np.cos(p(lat1)) * np.cos(p(lat2)) * np.sin(p(np.asarray(lon2) - lon1) / 2) ** 2
    km = 6371 * 2 * np.arcsin(np.sqrt(a))
    return km * DETOUR / WALK_KMH * 60


def store_time(t_area, alight_lat, alight_lon, rep_lat, rep_lon, lat, lon) -> np.ndarray:
    return t_area - walk_min(alight_lat, alight_lon, rep_lat, rep_lon) + walk_min(alight_lat, alight_lon, lat, lon)


def reach_flag(t: pd.Series, stable: float = STABLE_MIN, limit: float = REACH_MIN) -> pd.Series:
    return pd.Series(np.select([t <= stable, t <= limit], ["안정", "경계"], "제외"), index=t.index)


def gate(stores: pd.DataFrame, purpose: str) -> pd.Series:
    return stores.목적.eq(purpose) & ~stores.franchise.astype(bool)


def cached_path(lat: float, lon: float) -> tuple[float, float, float] | None:
    """캐시된 ODsay 응답의 (최단 totalTime, 마지막 탑승 구간 끝 위도, 경도). 캐시·경로가 없으면 None."""
    p = CACHE / f"{lat:.5f}_{lon:.5f}.json"
    if not p.exists():
        return None
    paths = json.loads(p.read_text()).get("result", {}).get("path", [])
    if not paths:
        return None
    best = min(paths, key=lambda x: x["info"]["totalTime"])
    rides = [s for s in best["subPath"] if s["trafficType"] != 3 and "endY" in s]
    return float(best["info"]["totalTime"]), float(rides[-1]["endY"]), float(rides[-1]["endX"])


def transit_stops() -> pd.DataFrame:
    bus = pd.read_excel(REPO / "data/raw/서울시버스노선별정류소정보_20260902.xlsx", usecols=["NODE_ID", "X좌표", "Y좌표"])
    metro = pd.read_csv(REPO / "data/raw/seoul_station_master_20260902.csv", encoding="cp949")
    stops = pd.concat([bus.rename(columns={"Y좌표": "lat", "X좌표": "lon"})[["lat", "lon"]],
                       metro.rename(columns={"위도": "lat", "경도": "lon"})[["lat", "lon"]]]).apply(pd.to_numeric, errors="coerce")
    return stops.dropna().drop_duplicates().reset_index(drop=True)


def area_reach() -> pd.DataFrame:
    areas = gpd.read_file(DATA / "commercial_area_accessibility/commercial_area_candidates_25pct.geojson")
    rep = areas.to_crs(5179).representative_point().to_crs(4326)
    a = pd.DataFrame({"area_code": areas.area_code.astype(str), "rep_lat": rep.y, "rep_lon": rep.x})
    a["straight_km"] = np.hypot((a.rep_lat - CAMPUS[0]) * 111, (a.rep_lon - CAMPUS[1]) * 88.2)
    measured = [cached_path(la, lo) for la, lo in zip(a.rep_lat, a.rep_lon)]
    a[["t_area", "alight_lat", "alight_lon"]] = [m if m else (np.nan,) * 3 for m in measured]
    a["reach_source"] = np.where(a.t_area.notna(), "측정(ODsay 캐시)", "추정(직선 회귀)")
    # 추정: 캐시 측정분으로 t = b0 + b1·직선km 를 맞춘다
    fit = a[a.t_area.notna() & (a.straight_km > WALK_COMPARE_KM)]
    b1, b0 = np.polyfit(fit.straight_km, fit.t_area, 1)
    est = a.t_area.isna()
    a.loc[est, "t_area"] = b0 + b1 * a.loc[est, "straight_km"]
    stops = transit_stops()
    tree_lat, tree_lon = stops.lat.to_numpy(), stops.lon.to_numpy()
    for i in a.index[est]:
        j = np.argmin(walk_min(a.at[i, "rep_lat"], a.at[i, "rep_lon"], tree_lat, tree_lon))
        a.loc[i, ["alight_lat", "alight_lon"]] = [tree_lat[j], tree_lon[j]]
    on_foot = walk_min(CAMPUS[0], CAMPUS[1], a.rep_lat, a.rep_lon)
    walk = (a.straight_km <= WALK_COMPARE_KM) & (on_foot < a.t_area)
    a.loc[walk, ["alight_lat", "alight_lon"]] = CAMPUS
    a.loc[walk, "t_area"] = on_foot[walk]
    a.loc[walk, "reach_source"] = "도보"
    print(f"t_area 회귀: {b0:.1f} + {b1:.2f}·km (캐시 {len(fit)}곳)", a.reach_source.value_counts().to_dict())
    wait = pd.read_csv(DATA / "campus_seoulcampus/seoulcampus_areas_reach_v1.csv", dtype={"area_code": str})[["area_code", "wait_risk"]]
    return a.merge(wait, on="area_code", how="left")


def main() -> None:
    stores = pd.read_csv(STORES, dtype={"area_code": str, "store_id": str, "소분류코드": str, "지점명": str, "층": str}, encoding="utf-8-sig")
    rank = pd.read_csv(DATA / "serendipity_ranking/serendipity_ranking_latest.csv", dtype={"area_code": str})
    inertia = pd.read_csv(DATA / "serendipity_ranking/inertia_baselines_top10.csv", dtype={"area_code": str})
    reach = area_reach()

    rank = rank[rank.eligible.astype(bool)][["purpose", "area_code", "mmr_rank", "score_rank", "mean_period_ratio"]]
    cand = pd.concat([rank[rank.purpose.eq(p)].merge(stores[gate(stores, p)], on="area_code") for p in PURPOSES], ignore_index=True)
    cand = cand.assign(group="candidate", in_k10=cand.mmr_rank.le(K), in_k20=cand.mmr_rank.le(K_SENS))

    inertia_areas = inertia[["purpose", "area_code"]].drop_duplicates()
    pool = stores[stores.area_code.isin(inertia_areas.area_code) & stores.목적.isin(INERTIA_PURPOSES)]
    sampled = pool.sample(frac=1, random_state=SEED).groupby("area_code").head(INERTIA_PER_AREA)
    ref = inertia_areas.merge(sampled, on="area_code").assign(group="inertia_ref")

    out = pd.concat([cand, ref], ignore_index=True).merge(reach, on="area_code", how="left")
    out["walk_from_rep"] = walk_min(out.rep_lat, out.rep_lon, out.lat, out.lon).round(1)
    out["reach_flag"] = reach_flag(out.walk_from_rep, REP_STABLE_MIN, REP_MAX_MIN)
    out["t_store_seoulcampus"] = store_time(out.t_area, out.alight_lat, out.alight_lon, out.rep_lat, out.rep_lon, out.lat, out.lon).round(1)
    out["seoulcampus_flag"] = reach_flag(out.t_store_seoulcampus)
    lead = ["group", "purpose", "area_code", "store_id", "walk_from_rep", "reach_flag", "mean_period_ratio", "mmr_rank", "in_k10", "in_k20",
            "t_store_seoulcampus", "seoulcampus_flag", "reach_source", "wait_risk", "t_area"]
    p2 = [c for c in stores.columns if c not in lead]
    out[lead + p2].to_csv(OUT / "store_candidates_v0.csv", index=False, encoding="utf-8-sig")
    report(out)


def report(out: pd.DataFrame) -> None:
    c = out[out.group.eq("candidate")]
    for name, sub in [("K=10", c[c.in_k10]), ("K=20", c[c.in_k20]), ("eligible 전체", c)]:
        print(f"[{name}] 후보 {len(sub):,} (고유 점포 {sub.store_id.nunique():,})", sub.purpose.value_counts().reindex(PURPOSES).to_dict())
    k = c[c.in_k10]
    per = k.groupby(["purpose", "area_code"]).size()
    print("K=10 상권당 후보 수(목적·상권):", per.groupby("purpose").agg(["median", "min", "max"]).to_dict("index"))
    print("K=10 reach_flag(대표점 도보) 비율:", k.reach_flag.value_counts(normalize=True).round(3).to_dict(),
          "| 참고 seoulcampus_flag:", k.seoulcampus_flag.value_counts(normalize=True).round(3).to_dict())
    print("K=10 대표점 도보 분위:", k.walk_from_rep.quantile([.5, .9, 1]).round(1).tolist())
    print("K=10 목적별 reach_flag:", k.groupby("purpose").reach_flag.value_counts(normalize=True).round(2).unstack().to_dict("index"))
    r = out[out.group.eq("inertia_ref")]
    print(f"관성 기준 점포 {len(r):,} 행, 고유 {r.store_id.nunique():,}, 상권 {r.area_code.nunique()}")
    p4 = pd.concat([k.store_id, r.store_id]).nunique()
    print(f"P4 수집 대상(K=10 후보 + 관성, 고유) {p4:,}")


if __name__ == "__main__":
    main()
