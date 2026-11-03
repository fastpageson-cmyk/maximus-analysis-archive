"""서울 공식 상권 786곳 안 점포 테이블 v0. 한 줄이 가게 한 곳이다.

    뼈대   = 상가(상권)정보 서울 2026-06, 상권 폴리곤 안(within)만. 폴리곤이 겹치면 면적이 작은 상권 하나에 둔다
    인허가 = 일반·휴게·제과 영업 중, EPSG:5174 → 4326. 음식 대분류 점포와 80m 안 similar(norm(상호))면 매칭, 여러 개면 가장 오래된 인허가
             상가정보에 없고 상권 안에 있는 인허가 점포는 source=license_only로 더한다(위생업태로 목적이 정해지는 것만)
    프랜차이즈 = 지점명 있음 ∨ 서울 상가정보에서 5번 이상 나오는 상호 접두어(is_franchise, KNOWN_CHAINS 포함) ∨ 상호 첫 단어 5번 이상
    태그   = 노포(≤2005) · 10년+(2006~2015) · 오래된 카페(휴게 CAFE_TYPES·제과점 ≤2015) · 착한가격(공공 좌표 80m·similar)
             희소도 = 1 − 상권 안 백분위(같은 상권 같은 소분류 점포 수)
    목적   = scripts/build_purpose_features.py PURPOSE_INDUSTRIES(서울시 상권분석 서비스업종 → 목적).
             상가정보 소분류·인허가 위생업태를 서비스업종으로 옮기는 대응표(SBIZ_TO_SERVICE, LICENSE_TO_SERVICE)를 거쳐 같은 표를 쓴다
출력: 데이터/가공/서울캠/seoul_store_table_v0.csv (커밋 금지)
      data/processed/store_level/match_audit_sample_v0.csv (매칭 감사 표본 50, 좌표 없음)
실행: ~/.venvs/maximus/bin/python -I scripts/campus/서울캠/build_seoul_store_table_v0.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(os.environ["MAXIMUS_WORKSPACE"]) if "MAXIMUS_WORKSPACE" in os.environ else next(p for p in Path(__file__).resolve().parents if (p / "데이터").is_dir())
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "scripts/campus/모현"))
sys.path.insert(0, str(REPO / "scripts/campus/서울캠"))
from build_mohyeon_hidden_stores_v0 import FRANCHISE_MIN_COUNT, NAME_MATCH_M, is_franchise, norm, similar  # noqa: E402
from build_mohyeon_recommendations_v1 import NOPO_YEAR, TENURE_YEAR  # noqa: E402
from build_purpose_features import map_industry_to_purpose  # noqa: E402
from build_seoulcampus_area_tags_v1 import CAFE_TYPES, SERVICES  # noqa: E402

RAW = ROOT / "데이터/원천/서울캠"
OUT = ROOT / "데이터/가공/서울캠"
PUBLIC = REPO / "data/processed/store_level"
AREAS = REPO / "data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.geojson"
SBIZ = RAW / "상가정보/sbiz_store_info_seoul_202606.csv"
GOODPRICE = RAW / "착한가격업소/goodprice_seoul_20261030.csv"
GOODPRICE_XY = RAW / "착한가격업소/geocode_public_goodprice_seoul_20261103.csv"
METRIC = 5179
AUDIT_N = 50
SEED = 42

# 상가정보 소분류 → 서울시 상권분석 서비스업종(PURPOSE_INDUSTRIES 키). 표에 없는 소분류는 목적 없음
SBIZ_TO_SERVICE = {
    **{f"I201{n:02d}": "한식음식점" for n in range(1, 14)}, "I20199": "한식음식점", "I20702": "한식음식점",
    "I20201": "중식음식점", "I20202": "중식음식점",
    "I20301": "일식음식점", "I20302": "일식음식점", "I20303": "일식음식점", "I20399": "일식음식점",
    "I20401": "양식음식점", "I20402": "양식음식점", "I20403": "양식음식점", "I20499": "양식음식점",
    "I20501": "양식음식점", "I20599": "양식음식점", "I20601": "양식음식점",
    "I21001": "제과점", "I21002": "제과점", "I21003": "패스트푸드점", "I21004": "패스트푸드점",
    "I21005": "분식전문점", "I21006": "치킨전문점", "I21007": "분식전문점", "I21099": "분식전문점",
    "I21008": "커피-음료", "I21201": "커피-음료", "I21103": "호프-간이주점", "I21104": "일반주점",
    "G21301": "서적", "G21302": "문구", "G20901": "일반의류", "G20902": "일반의류", "G20905": "일반의류",
    "G20903": "유아의류", "G20904": "한복점", "G20911": "가방", "G20910": "신발", "G21503": "화장품",
    "G21701": "시계및귀금속", "G20404": "슈퍼마켓", "G20405": "편의점", "G20803": "가전제품", "G20802": "핸드폰",
    "G21101": "가구", "G21602": "안경", "G21306": "완구", "G21901": "화초", "G22001": "애완동물",
    "G21304": "운동/경기용품", "G21305": "운동/경기용품", "G20506": "청과상", "G20501": "미곡판매",
    "G20504": "수산물판매", "G20505": "수산물판매", "G20503": "육류판매", "G20509": "반찬가게", "G21501": "의약품",
    "G20202": "자동차부품", "G21201": "조명용품", "G20906": "섬유제품", "G20909": "섬유제품", "G21002": "인테리어",
    "G21001": "철물점", "G21801": "예술품", "G21203": "악기",
    "P10501": "일반교습학원", "P10615": "외국어학원", "P10627": "컴퓨터학원", "P10609": "예술학원", "P10611": "예술학원",
    "P10613": "예술학원", "P10601": "스포츠강습", "P10603": "스포츠강습", "R10202": "독서실",
    "R10407": "노래방", "R10406": "PC방", "R10310": "당구장", "R10311": "골프연습장", "R10309": "볼링장",
    "R10405": "기타오락장", "R10404": "전자게임장", "R10402": "DVD방",
    **{c: "스포츠클럽" for c in ["R10306", "R10307", "R10308", "R10312", "R10313", "R10314", "R10316"]},
    "I10101": "호텔", "I10102": "여관",
}
# 인허가 위생업태 → 서비스업종(license_only 점포용). '기타'·편의점·백화점처럼 업종을 알 수 없거나 상가정보와 겹치는 것은 뺀다
LICENSE_TO_SERVICE = {
    **dict.fromkeys(["한식", "식육(숯불구이)", "횟집", "냉면집", "탕류(보신용)", "복어취급", "뷔페식"], "한식음식점"),
    "중국식": "중식음식점", "일식": "일식음식점",
    **dict.fromkeys(["경양식", "외국음식전문점(인도,태국등)", "패밀리레스트랑"], "양식음식점"),
    "분식": "분식전문점", "김밥(도시락)": "분식전문점", "패스트푸드": "패스트푸드점", "통닭(치킨)": "치킨전문점",
    "호프/통닭": "호프-간이주점", **dict.fromkeys(["정종/대포집/소주방", "감성주점", "라이브카페"], "일반주점"),
    **dict.fromkeys(["까페", "커피숍", "다방", "전통찻집", "떡카페", "아이스크림"], "커피-음료"),
    "과자점": "제과점", "제과점영업": "제과점",
}
COLUMNS = ["store_id", "상호", "지점명", "소분류코드", "소분류명", "목적", "area_code", "area_name", "lat", "lon", "층",
           "license_year", "license_service", "nopo", "tenure10", "old_cafe", "goodprice", "rarity", "franchise", "source"]


def load_areas() -> gpd.GeoDataFrame:
    a = gpd.read_file(AREAS)[["area_code", "area_name", "geometry"]].assign(area_code=lambda d: d.area_code.astype(str))
    return a.assign(poly_m2=a.to_crs(METRIC).area)


def in_areas(pts: gpd.GeoDataFrame, areas: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """폴리곤 안 점만 남기고, 겹치는 폴리곤에 든 점은 면적이 작은 상권 하나에 둔다."""
    j = gpd.sjoin(pts, areas, predicate="within").sort_values("poly_m2")
    return j[~j.index.duplicated()].drop(columns=["index_right", "poly_m2"]).sort_index()


def load_sbiz(areas: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, pd.Series]:
    cols = ["상가업소번호", "상호명", "지점명", "상권업종대분류명", "상권업종소분류코드", "상권업종소분류명", "층정보", "경도", "위도"]
    s = pd.read_csv(SBIZ, dtype=str, usecols=cols)
    names = s.상호명.fillna("")
    g = gpd.GeoDataFrame(s, geometry=gpd.points_from_xy(s.경도.astype(float), s.위도.astype(float)), crs=4326)
    return in_areas(g, areas), names


def load_licenses(areas: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    lic = pd.concat([pd.read_csv(RAW / f"인허가/{v}_seoul_active_20261030.csv", dtype=str).assign(license_service=v) for v in SERVICES],
                    ignore_index=True).drop_duplicates("MNG_NO")
    lic = lic[lic.CRD_INFO_X.notna() & lic.CRD_INFO_Y.notna()]
    lic["license_year"] = pd.to_numeric(lic.LCPMT_YMD.str[:4], errors="coerce")
    lic["key"] = lic.BPLC_NM.map(norm)
    g = gpd.GeoDataFrame(lic, geometry=gpd.points_from_xy(lic.CRD_INFO_X.astype(float), lic.CRD_INFO_Y.astype(float)), crs=5174).to_crs(4326)
    return in_areas(g[["MNG_NO", "BPLC_NM", "key", "license_year", "license_service", "SNTTN_BZSTAT_NM", "geometry"]], areas)


def name_pairs(left: gpd.GeoDataFrame, right: gpd.GeoDataFrame, lkey: str, rkey: str) -> pd.DataFrame:
    """80m 안이면서 similar(정규화 상호)인 (left 행, right 행, 거리) 쌍."""
    lm = left[[lkey, "geometry"]].rename(columns={lkey: "lk"}).to_crs(METRIC)
    rm = right[[rkey, "geometry"]].rename(columns={rkey: "rk"}).to_crs(METRIC)
    j = gpd.sjoin(lm, rm.assign(geometry=rm.buffer(NAME_MATCH_M)), predicate="within")
    j = j[[similar(a, b) for a, b in zip(j.lk, j.rk)]]
    dist = lm.geometry.loc[j.index].distance(rm.geometry.loc[j.index_right], align=False).to_numpy()
    return pd.DataFrame({"left": j.index, "right": j.index_right.to_numpy(), "dist_m": dist})


def franchise_flags(keys: pd.Series, names: pd.Series, has_branch: pd.Series, all_names: pd.Series) -> pd.Series:
    all_keys = all_names.map(norm)
    brands = set(all_keys.value_counts().loc[lambda s: s >= FRANCHISE_MIN_COUNT].index)
    first_counts = all_names.str.split().str[0].value_counts()
    first = names.fillna("").str.split().str[0].fillna("")
    return has_branch | first.map(first_counts).fillna(0).ge(FRANCHISE_MIN_COUNT) | keys.map(lambda k: is_franchise(k, brands))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    PUBLIC.mkdir(parents=True, exist_ok=True)
    areas = load_areas()
    sbiz, all_names = load_sbiz(areas)
    sbiz["key"] = sbiz.상호명.map(norm)
    lic = load_licenses(areas)

    # 인허가 매칭: 음식 대분류 점포만, 가장 오래된 인허가 하나
    food = sbiz[sbiz.상권업종대분류명.eq("음식")]
    pairs = name_pairs(food, lic, "key", "key").merge(lic[["license_year"]], left_on="right", right_index=True)
    best = pairs.sort_values(["license_year", "dist_m"], na_position="last").drop_duplicates("left").set_index("left")
    m = lic.loc[best.right].set_axis(best.index)
    sbiz = sbiz.join(m[["license_year", "license_service", "SNTTN_BZSTAT_NM", "BPLC_NM"]]).join(best.dist_m)

    stores = pd.DataFrame({
        "store_id": sbiz.상가업소번호, "상호": sbiz.상호명, "지점명": sbiz.지점명, "소분류코드": sbiz.상권업종소분류코드,
        "소분류명": sbiz.상권업종소분류명, "목적": sbiz.상권업종소분류코드.map(SBIZ_TO_SERVICE).map(map_industry_to_purpose),
        "area_code": sbiz.area_code, "area_name": sbiz.area_name, "lat": sbiz.geometry.y, "lon": sbiz.geometry.x, "층": sbiz.층정보,
        "license_year": sbiz.license_year, "license_service": sbiz.license_service, "위생업태": sbiz.SNTTN_BZSTAT_NM,
        "key": sbiz.key, "source": "sbiz", "인허가상호": sbiz.BPLC_NM, "dist_m": sbiz.dist_m,
    })
    only = lic[~lic.index.isin(pairs.right) & lic.SNTTN_BZSTAT_NM.isin(LICENSE_TO_SERVICE)]
    stores = pd.concat([stores, pd.DataFrame({
        "store_id": "L" + only.MNG_NO, "상호": only.BPLC_NM, "소분류명": only.SNTTN_BZSTAT_NM,
        "목적": only.SNTTN_BZSTAT_NM.map(LICENSE_TO_SERVICE).map(map_industry_to_purpose),
        "area_code": only.area_code, "area_name": only.area_name, "lat": only.geometry.y, "lon": only.geometry.x,
        "license_year": only.license_year, "license_service": only.license_service, "위생업태": only.SNTTN_BZSTAT_NM,
        "key": only.key, "source": "license_only"})], ignore_index=True)

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

    group = stores.소분류코드.fillna("L:" + stores.소분류명.fillna(""))
    n_same = stores.groupby([stores.area_code, group]).store_id.transform("size")
    stores["rarity"] = 1 - n_same.groupby(stores.area_code).rank(pct=True)
    stores["license_year"] = stores.license_year.astype("Int64")
    stores[COLUMNS].to_csv(OUT / "seoul_store_table_v0.csv", index=False, encoding="utf-8-sig")

    matched = stores[stores.source.eq("sbiz") & stores.license_year.notna()]
    audit = matched.sample(AUDIT_N, random_state=SEED)
    audit = pd.DataFrame({"상호": audit.상호, "소분류명": audit.소분류명, "인허가 상호": audit.인허가상호,
                          "인허가 연도": audit.license_year, "거리_m": audit.dist_m.round(1), "판정": ""})
    audit.to_csv(PUBLIC / "match_audit_sample_v0.csv", index=False, encoding="utf-8-sig")
    report(stores, sbiz, lic, areas)


def report(stores: pd.DataFrame, sbiz: pd.DataFrame, lic: pd.DataFrame, areas: gpd.GeoDataFrame) -> None:
    n_all = sum(1 for _ in open(SBIZ, encoding="utf-8")) - 1
    food = stores.source.eq("sbiz") & stores.license_service.notna()
    n_food = int((stores.source.eq("sbiz") & stores.소분류코드.str.startswith("I2", na=False)).sum())
    print(f"점포 {len(stores):,} (sbiz {int(stores.source.eq('sbiz').sum()):,}, license_only {int(stores.source.eq('license_only').sum()):,})")
    print(f"상권 결합: 상가정보 서울 {n_all:,} 중 {len(sbiz):,} ({len(sbiz) / n_all:.1%}), 상권 {stores.area_code.nunique()}/{len(areas)}")
    print(f"인허가 매칭: 음식 점포 {n_food:,} 중 {int(food.sum()):,} ({food.sum() / n_food:.1%}), 상권 안 인허가 {len(lic):,}")
    print(f"프랜차이즈 {stores.franchise.mean():.1%} (음식 {stores.loc[stores.소분류코드.str.startswith('I2', na=False), 'franchise'].mean():.1%})")
    nf = ~stores.franchise
    print("태그(전체/비프랜차이즈):", {t: (int(stores[t].sum()), int((stores[t] & nf).sum())) for t in ["nopo", "tenure10", "old_cafe", "goodprice"]})
    print("목적별:", stores.목적.value_counts(dropna=False).to_dict())
    print("목적별 비프랜차이즈:", stores[nf].목적.value_counts().to_dict())
    tags = pd.read_csv(REPO / "data/processed/campus_seoulcampus/seoulcampus_area_tags_v1.csv", dtype={"area_code": str}).set_index("area_code")
    new = stores[nf].groupby("area_code")[["nopo", "tenure10"]].sum().rename(columns={"tenure10": "n_10yr", "nopo": "n_nopo"})
    cmp = tags[["n_nopo", "n_10yr"]].join(new, rsuffix="_new").fillna(0)
    for c in ["n_nopo", "n_10yr"]:
        d = cmp[f"{c}_new"] - cmp[c]
        print(f"{c} 차이(새−v1): 합계 {int(cmp[c].sum())}→{int(cmp[c + '_new'].sum())}, 분위 {d.quantile([0, .1, .5, .9, 1]).round(1).tolist()}, 같음 {(d == 0).mean():.1%}")


if __name__ == "__main__":
    main()
