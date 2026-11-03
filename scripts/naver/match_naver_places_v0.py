"""P3 점포(식사·카페·공부 K=10 후보 + 관성 기준)를 네이버 플레이스 장소에 연결한다 v0.

    검색   = map.naver.com instant-search, 검색어 = norm(상호), coords = 점포 좌표. 결과가 없으면 상호 + 도로명(없으면 법정동)
             (자동완성 검색이라 도로명을 붙이면 오히려 못 찾는다: 2026-11-03 시험)
    판정   = 80m 안 ∧ similar(norm) → exact, 80m 안만 → fuzzy, 없으면 none. 여럿이면 exact 우선, 그다음 가까운 곳
    요청   = 쿠키·캡차 토큰 없이, 단일 스레드, 2~3초 + 무작위 지연. 403·429·캡차 응답은 지수 백오프, 3번 연속이면 멈춤
    캐시   = 데이터/캐시/naver_search/{store_id}[_road].json (검색 응답 원본, 장소 정보만 있음). 재실행하면 캐시가 있는 검색은 건너뜀
출력: 데이터/가공/서울캠/naver_place_match_v0.csv (커밋 금지)
      data/processed/store_level/naver_match_audit_sample_v0.csv (무작위 50곳, place_id·좌표 없음)
실행: ~/.venvs/maximus/bin/python -I scripts/naver/match_naver_places_v0.py --limit 1   (시험은 --limit으로)
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests

REPO = Path(__file__).resolve().parents[2]
ROOT = Path(os.environ["MAXIMUS_WORKSPACE"]) if "MAXIMUS_WORKSPACE" in os.environ else next((p for p in REPO.parents if (p / "데이터").is_dir()), REPO.parent)
sys.path.insert(0, str(REPO / "scripts/campus/모현"))
from build_mohyeon_hidden_stores_v0 import NAME_MATCH_M, norm, similar  # noqa: E402

OUT = ROOT / "데이터/가공/서울캠"
CACHE = ROOT / "데이터/캐시/naver_search"
CANDIDATES = OUT / "store_candidates_v0.csv"
SBIZ = ROOT / "데이터/원천/서울캠/상가정보/sbiz_store_info_seoul_202606.csv"
LICENSE_DIR = ROOT / "데이터/원천/서울캠/인허가"
PUBLIC = REPO / "data/processed/store_level"
SEARCH_URL = "https://map.naver.com/p/api/search/instant-search"
TARGET_PURPOSES = {"식사", "카페", "공부"}
DELAY_S, JITTER_S = 2.0, 1.0
MAX_FAILS = 3
AUDIT_N, SEED = 50, 42
HEADERS = {"Accept": "application/json", "Accept-Language": "ko", "Referer": "https://map.naver.com/"}
ROAD = re.compile(r"([가-힣0-9]+(?:로|길))(?:\s|$)")


class Blocked(RuntimeError):
    """403·429·캡차가 연속으로 와서 멈춘다."""


class Polite:
    """단일 스레드 요청기: 매 요청 전 2~3초 + 무작위 지연, 차단 응답은 지수 백오프, 3번 연속이면 Blocked."""

    def __init__(self, delay_s: float = DELAY_S, backoff_s: float = DELAY_S) -> None:
        self.session = requests.Session()
        self.fails = 0
        self.delay_s, self.backoff_s = delay_s, backoff_s

    def call(self, method: str, url: str, **kw) -> dict:
        while True:
            time.sleep(self.delay_s + random.uniform(0, max(JITTER_S, self.delay_s / 2)))
            r = self.session.request(method, url, headers={**HEADERS, **kw.pop("headers", {})}, timeout=20, **kw)
            blocked = r.status_code in (403, 429) or "captcha" in r.text[:2000].lower()
            if not blocked and r.ok:
                self.fails = 0
                return r.json()
            self.fails += 1
            if self.fails >= MAX_FAILS:
                raise Blocked(f"{url} {r.status_code} 연속 {self.fails}번: {r.text[:200]}")
            print(f"  {r.status_code}, {self.backoff_s * 2 ** self.fails:.0f}초 쉬고 다시", flush=True)
            time.sleep(self.backoff_s * 2 ** self.fails)


def find_places(obj) -> list[dict]:
    """응답 어디에 있든 id·title·x·y를 가진 장소 dict를 모은다(응답 구조가 바뀌어도 버티게)."""
    found = []
    if isinstance(obj, dict):
        if {"id", "title", "x", "y"} <= obj.keys():
            found.append({k: obj.get(k) for k in ["id", "title", "x", "y", "roadAddress", "ctg"]})
        for v in obj.values():
            found += find_places(v)
        found = list({p["id"]: p for p in found}.values())
    elif isinstance(obj, list):
        for v in obj:
            found += find_places(v)
    return found


def dist_m(lat1, lon1, lat2, lon2):
    p = np.radians
    a = np.sin(p(lat2 - lat1) / 2) ** 2 + np.cos(p(lat1)) * np.cos(p(lat2)) * np.sin(p(lon2 - lon1) / 2) ** 2
    return 6371000 * 2 * np.arcsin(np.sqrt(a))


def judge(name: str, lat: float, lon: float, places: list[dict]) -> dict:
    """exact(80m ∧ 상호 유사) → fuzzy(80m) → none. 같은 등급이면 가까운 곳."""
    best = None
    for p in places:
        d = float(dist_m(lat, lon, float(p["y"]), float(p["x"])))
        if d > NAME_MATCH_M:
            continue
        status = "exact" if similar(norm(name), norm(p["title"])) else "fuzzy"
        key = (status != "exact", d)
        if best is None or key < best[0]:
            best = (key, {"place_id": str(p["id"]), "naver_name": p["title"], "dist_m": round(d, 1), "match_status": status})
    return best[1] if best else {"place_id": None, "naver_name": None, "dist_m": None, "match_status": "none"}


def road_of(addr) -> str | None:
    m = ROAD.search(str(addr)) if isinstance(addr, str) else None
    return m.group(1) if m else None


def targets() -> pd.DataFrame:
    c = pd.read_csv(CANDIDATES, dtype={"store_id": str, "area_code": str}, low_memory=False)
    c = c[(c.group.eq("candidate") & c.in_k10.astype(bool) & c.purpose.isin(TARGET_PURPOSES)) | c.group.eq("inertia_ref")]
    t = c.drop_duplicates("store_id")[["store_id", "상호", "소분류명", "lat", "lon"]]
    s = pd.read_csv(SBIZ, dtype=str, usecols=["상가업소번호", "도로명", "법정동명"]).rename(columns={"상가업소번호": "store_id"})
    lic = pd.concat([pd.read_csv(f, dtype=str, usecols=["MNG_NO", "ROAD_NM_ADDR"]) for f in LICENSE_DIR.glob("*_seoul_active_*.csv")])
    lic = lic.assign(store_id="L" + lic.MNG_NO, 도로명=lic.ROAD_NM_ADDR)[["store_id", "도로명"]]
    t = t.merge(pd.concat([s, lic]).drop_duplicates("store_id"), on="store_id", how="left")
    t["query"] = [f"{norm(n)} {road_of(r) or (d if isinstance(d, str) else '')}".strip() for n, r, d in zip(t.상호, t.도로명, t.법정동명)]
    return t


def cached_search(client: Polite, path: Path, query: str, lat: float, lon: float, debug: bool) -> list[dict]:
    if path.exists():
        data = json.loads(path.read_text())
    else:
        data = client.call("GET", SEARCH_URL, params={"query": query, "coords": f"{lat},{lon}"})
        path.write_text(json.dumps(data, ensure_ascii=False))
    if debug:
        print(f"[debug] {query!r} →", json.dumps(data, ensure_ascii=False)[:800])
    return find_places(data)


def search(client: Polite, store, debug: bool = False) -> list[dict]:
    """정규화 상호로 찾고, 없으면 상호 + 도로명으로 다시 찾는다."""
    places = cached_search(client, CACHE / f"{store.store_id}.json", norm(store.상호), store.lat, store.lon, debug)
    if not places and store.query != norm(store.상호):
        places = cached_search(client, CACHE / f"{store.store_id}_road.json", store.query, store.lat, store.lon, debug)
    return places


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="앞에서부터 N곳만(시험용)")
    ap.add_argument("--debug", action="store_true", help="검색 응답 앞부분 출력")
    args = ap.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    t = targets()
    t = t.head(args.limit) if args.limit else t
    client, rows = Polite(), []
    try:
        for i, s in enumerate(t.itertuples(index=False), 1):
            rows.append({"store_id": s.store_id, **judge(s.상호, s.lat, s.lon, search(client, s, args.debug))})
            if i % 50 == 0:
                print(f"{i}/{len(t)} {datetime.now():%H:%M:%S}", flush=True)
    except Blocked as e:
        print("멈춤:", e)
    m = pd.DataFrame(rows, columns=["store_id", "place_id", "naver_name", "dist_m", "match_status"])
    m.to_csv(OUT / "naver_place_match_v0.csv", index=False, encoding="utf-8-sig")
    print(f"연결 {len(m)}/{len(t)}", m.match_status.value_counts().to_dict())
    if len(m) >= AUDIT_N:
        a = m.merge(t[["store_id", "상호", "소분류명"]], on="store_id").sample(AUDIT_N, random_state=SEED)
        a.assign(판정="").rename(columns={"naver_name": "네이버 장소명"})[["상호", "소분류명", "네이버 장소명", "dist_m", "match_status", "판정"]].to_csv(
            PUBLIC / "naver_match_audit_sample_v0.csv", index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
