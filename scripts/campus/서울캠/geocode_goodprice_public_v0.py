"""서울 착한가격업소에 공공데이터 좌표를 붙인다(카카오 응답 대신).

    도로명주소를 '구 도로명 건물번호' 키로 줄이고, 같은 키의 상가(상권)정보 서울 점포 좌표(경도·위도) 중앙값을 쓴다.
    상가정보에 없으면 인허가 3종(ROAD_NM_ADDR, EPSG:5174) 좌표 중앙값으로 채운다. 둘 다 없으면 빈칸.
    키 없는 방법이라 juso·브이월드 지오코더를 대신한다. 건물 단위 좌표라 같은 건물 안 점포는 같은 점이 된다.
출력: 데이터/원천/서울캠/착한가격업소/geocode_public_goodprice_seoul_YYYYMMDD.csv (번호, lat, lon, geocode_by)
실행: ~/.venvs/maximus/bin/python -I scripts/campus/서울캠/geocode_goodprice_public_v0.py
"""

from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(os.environ["MAXIMUS_WORKSPACE"]) if "MAXIMUS_WORKSPACE" in os.environ else next(p for p in Path(__file__).resolve().parents if (p / "데이터").is_dir())
RAW = ROOT / "데이터/원천/서울캠"
SBIZ = RAW / "상가정보/sbiz_store_info_seoul_202606.csv"
GOODPRICE = RAW / "착한가격업소/goodprice_seoul_20261030.csv"
SERVICES = ["general_restaurants", "rest_cafes", "bakeries"]
ADDR = re.compile(r"([가-힣]+구)\s+([가-힣0-9]+(?:로|길)(?:\s*[0-9]+[가-힣]?(?:번)?길)?)\s*(지하\s*)?([0-9]+(?:-[0-9]+)?)")


def addr_key(a: object) -> str | None:
    """'서울특별시 종로구 지봉로12길 6 (숭인동) 1층' → '종로구 지봉로12길 6'"""
    m = ADDR.search(re.sub(r"\(.*?\)", "", str(a)))
    return f"{m.group(1)} {m.group(2).replace(' ', '')} {m.group(4)}" if m else None


def coord_table(df: pd.DataFrame, addr: str, lat: str, lon: str) -> pd.DataFrame:
    return df.assign(k=df[addr].map(addr_key)).dropna(subset=["k"]).groupby("k")[[lat, lon]].median().set_axis(["lat", "lon"], axis=1)


def main() -> None:
    s = pd.read_csv(SBIZ, dtype={"도로명주소": str}, usecols=["도로명주소", "경도", "위도"])
    sbiz = coord_table(s, "도로명주소", "위도", "경도")
    lic = pd.concat([pd.read_csv(RAW / f"인허가/{v}_seoul_active_20261030.csv", dtype=str, usecols=["ROAD_NM_ADDR", "CRD_INFO_X", "CRD_INFO_Y"]) for v in SERVICES])
    lic = lic.dropna(subset=["CRD_INFO_X", "CRD_INFO_Y"])
    pts = gpd.GeoSeries(gpd.points_from_xy(lic.CRD_INFO_X.astype(float), lic.CRD_INFO_Y.astype(float)), crs=5174).to_crs(4326)
    lic = coord_table(lic.assign(lat=pts.y.values, lon=pts.x.values), "ROAD_NM_ADDR", "lat", "lon")

    gp = pd.read_csv(GOODPRICE, dtype=str)[["번호", "주소"]]
    gp["k"] = gp.주소.map(addr_key)
    out = gp.join(sbiz, on="k").assign(geocode_by=lambda d: d.lat.notna().map({True: "sbiz_addr", False: None}))
    miss = out.lat.isna()
    out.loc[miss, ["lat", "lon"]] = gp.loc[miss, ["k"]].join(lic, on="k")[["lat", "lon"]].values
    out.loc[miss & out.lat.notna(), "geocode_by"] = "license_addr"
    path = RAW / f"착한가격업소/geocode_public_goodprice_seoul_{date.today():%Y%m%d}.csv"
    out[["번호", "lat", "lon", "geocode_by"]].to_csv(path, index=False, encoding="utf-8-sig")
    print(path.name, len(out), out.geocode_by.value_counts(dropna=False).to_dict())


if __name__ == "__main__":
    main()
