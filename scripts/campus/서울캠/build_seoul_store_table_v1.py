"""서울 공식 상권 786곳 안 점포 테이블 v1. v0(build_seoul_store_table_v0.py)와 같은 뼈대·매칭·태그에 store_rules_v1 규칙을 더한다.

    업종 보정 = 상호 키워드(name_rule) > 인허가 위생업태(license, 상가정보와 그룹이 다를 때) > 상가정보(sbiz)
               소분류명은 보정값, 소분류명_원은 원래 값. category_fixed, category_source(sbiz / license / name_rule)
    목적     = 점포 단계 목적(store_rules_v1.store_purpose). 공부 = 독서실/스터디 카페 (+ 서점·북카페). 학원·문구는 목적 없음
    제외     = 비목적지(소분류 패턴 · 상호 키워드 · 경계 업종 끔)는 목적을 비우고 exclude_reason에 사유
    희소도   = 1 − 상권 안 백분위(같은 상권 같은 '보정' 소분류명 점포 수) = rarity_raw. 생활형 소분류는 rarity 0(destination=False)
출력: 데이터/가공/서울캠/seoul_store_table_v1.csv (커밋 금지)
실행: ~/.venvs/maximus/bin/python -I scripts/campus/서울캠/build_seoul_store_table_v1.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import store_rules_v1 as rules  # noqa: E402
from build_seoul_store_table_v0 import (CAFE_TYPES, GOODPRICE, GOODPRICE_XY, LICENSE_TO_SERVICE, NOPO_YEAR, OUT,  # noqa: E402
                                        SBIZ_TO_SERVICE, TENURE_YEAR, franchise_flags, load_areas, load_licenses, load_sbiz,
                                        name_pairs, norm)

COLUMNS = ["store_id", "상호", "지점명", "소분류코드", "소분류명", "소분류명_원", "category_fixed", "category_source", "목적",
           "목적_보정전", "exclude_reason", "destination", "area_code", "area_name", "lat", "lon", "층", "license_year",
           "license_service", "위생업태", "nopo", "tenure10", "old_cafe", "goodprice", "rarity", "rarity_raw", "franchise", "source"]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    areas = load_areas()
    sbiz, all_names = load_sbiz(areas)
    sbiz["key"] = sbiz.상호명.map(norm)
    lic = load_licenses(areas)

    food = sbiz[sbiz.상권업종대분류명.eq("음식")]
    pairs = name_pairs(food, lic, "key", "key").merge(lic[["license_year"]], left_on="right", right_index=True)
    best = pairs.sort_values(["license_year", "dist_m"], na_position="last").drop_duplicates("left").set_index("left")
    m = lic.loc[best.right].set_axis(best.index)
    sbiz = sbiz.join(m[["license_year", "license_service", "SNTTN_BZSTAT_NM"]])

    stores = pd.DataFrame({
        "store_id": sbiz.상가업소번호, "상호": sbiz.상호명, "지점명": sbiz.지점명, "소분류코드": sbiz.상권업종소분류코드,
        "소분류명": sbiz.상권업종소분류명, "service": sbiz.상권업종소분류코드.map(SBIZ_TO_SERVICE),
        "food": sbiz.상권업종소분류코드.str.startswith("I2", na=False),
        "area_code": sbiz.area_code, "area_name": sbiz.area_name, "lat": sbiz.geometry.y, "lon": sbiz.geometry.x, "층": sbiz.층정보,
        "license_year": sbiz.license_year, "license_service": sbiz.license_service, "위생업태": sbiz.SNTTN_BZSTAT_NM,
        "key": sbiz.key, "source": "sbiz",
    })
    only = lic[~lic.index.isin(pairs.right) & lic.SNTTN_BZSTAT_NM.isin(LICENSE_TO_SERVICE)]
    stores = pd.concat([stores, pd.DataFrame({
        "store_id": "L" + only.MNG_NO, "상호": only.BPLC_NM, "소분류명": only.SNTTN_BZSTAT_NM,
        "service": only.SNTTN_BZSTAT_NM.map(LICENSE_TO_SERVICE), "food": True,
        "area_code": only.area_code, "area_name": only.area_name, "lat": only.geometry.y, "lon": only.geometry.x,
        "license_year": only.license_year, "license_service": only.license_service, "위생업태": only.SNTTN_BZSTAT_NM,
        "key": only.key, "source": "license_only"})], ignore_index=True)
    stores = rules.apply_rules(stores)

    stores["franchise"] = franchise_flags(stores.key, stores.상호, stores.지점명.notna(), all_names)
    y = stores.license_year
    stores["nopo"] = y.le(NOPO_YEAR)
    stores["tenure10"] = y.gt(NOPO_YEAR) & y.le(TENURE_YEAR)
    cafe_lic = stores.license_service.eq("bakeries") | (stores.license_service.eq("rest_cafes") & stores.위생업태.isin(CAFE_TYPES))
    stores["old_cafe"] = cafe_lic & y.le(TENURE_YEAR)

    gp = pd.read_csv(GOODPRICE, dtype=str).merge(pd.read_csv(GOODPRICE_XY, dtype={"번호": str}), on="번호").dropna(subset=["lat"])
    gp = gpd.GeoDataFrame(gp.assign(key=gp.업소명.map(norm)), geometry=gpd.points_from_xy(gp.lon, gp.lat), crs=4326)
    pts = gpd.GeoDataFrame(stores[["key"]], geometry=gpd.points_from_xy(stores.lon, stores.lat), crs=4326)
    stores["goodprice"] = stores.index.isin(name_pairs(pts, gp, "key", "key").left)

    n_same = stores.groupby([stores.area_code, stores.소분류명.fillna("")]).store_id.transform("size")
    stores["rarity_raw"] = 1 - n_same.groupby(stores.area_code).rank(pct=True)
    stores["rarity"] = stores.rarity_raw.where(stores.destination, 0.0)
    stores["license_year"] = stores.license_year.astype("Int64")
    stores[COLUMNS].to_csv(OUT / "seoul_store_table_v1.csv", index=False, encoding="utf-8-sig")
    report(stores)


def report(stores: pd.DataFrame) -> None:
    print(f"점포 {len(stores):,} (sbiz {int(stores.source.eq('sbiz').sum()):,}, license_only {int(stores.source.eq('license_only').sum()):,})")
    print("category_source:", stores.category_source.value_counts().to_dict(), "| 보정", int(stores.category_fixed.sum()))
    fixed = stores[stores.category_fixed]
    print("보정 전→후 상위 15:\n", fixed.groupby(["소분류명_원", "소분류명"]).size().sort_values(ascending=False).head(15).to_string())
    print("목적 변화(보정 전 v0 대응표 기준은 v0 테이블과 비교):", pd.crosstab(stores.목적_보정전.fillna("-"), stores.목적.fillna("-")).to_dict())
    print("제외 사유:", stores.exclude_reason.value_counts().to_dict())
    print("목적별:", stores.목적.value_counts(dropna=False).to_dict())
    print("목적별 비프랜차이즈:", stores[~stores.franchise].목적.value_counts().to_dict())
    print("생활형(희소도 0):", int((~stores.destination & stores.목적.notna()).sum()))


if __name__ == "__main__":
    main()
