# 점포 단위(store-level) 산출물

설계: `docs/store_level_recommendation_options.md`. 원천 출처: `docs/campus/seoul_store_raw_sources.md`.
점포 테이블 자체는 원천(상가정보·인허가)을 그대로 담고 있어 **커밋하지 않는다.** 이 폴더에는 공개해도 되는 감사 표본과 설명만 둔다.

## 서울 점포 테이블 v0 (로컬)

`<작업 폴더>/데이터/가공/서울캠/seoul_store_table_v0.csv`. 서울 공식 상권 786곳 안 점포, 한 줄이 가게 한 곳이다.

실행(저장소 루트에서):

```bash
~/.venvs/maximus/bin/python -I scripts/campus/서울캠/geocode_goodprice_public_v0.py   # 착한가격 공공 좌표(한 번)
~/.venvs/maximus/bin/python -I scripts/campus/서울캠/build_seoul_store_table_v0.py
```

| 열 | 설명 |
|---|---|
| store_id | 상가업소번호. license_only는 `L` + 인허가 관리번호 |
| 상호, 지점명 | 상가정보 상호명·지점명. license_only는 인허가 사업장명, 지점명 빈칸 |
| 소분류코드, 소분류명 | 상가정보 상권업종 소분류. license_only는 코드 빈칸, 이름에 인허가 위생업태 |
| 목적 | 식사·카페·공부·쇼핑·여가문화 또는 빈칸. `scripts/build_purpose_features.py`의 `PURPOSE_INDUSTRIES`(서울시 상권분석 서비스업종 → 목적)를 쓴다. 소분류·위생업태를 서비스업종으로 옮기는 대응표는 스크립트의 `SBIZ_TO_SERVICE`, `LICENSE_TO_SERVICE` |
| area_code, area_name | 상권(within). 폴리곤이 겹치면(49쌍) 면적이 작은 상권 하나 |
| lat, lon | WGS84. 상가정보 좌표, license_only는 인허가 좌표(EPSG:5174 변환) |
| 층 | 상가정보 층정보 |
| license_year | 매칭된 인허가 연도(80m 안 similar(norm(상호)), 여러 개면 가장 오래된 것). 음식 대분류만 매칭 |
| license_service | general_restaurants / rest_cafes / bakeries |
| nopo | license_year ≤ 2005 |
| tenure10 | 2006 ≤ license_year ≤ 2015 |
| old_cafe | 휴게음식점(커피숍·다방·과자점·전통찻집·떡카페)·제과점 인허가 중 ≤ 2015 |
| goodprice | 착한가격업소(공공 좌표) 80m 안 similar 상호. 음식 외 업종 포함 |
| rarity | 1 − 상권 안 백분위(같은 상권 같은 소분류 점포 수). 1에 가까울수록 그 상권에서 드문 업종 |
| franchise | 지점명 있음, 서울 상가정보에서 5번 이상 나오는 상호 접두어(`is_franchise`, KNOWN_CHAINS 포함), 상호 첫 단어 5번 이상 중 하나 |
| source | sbiz / license_only |

### 한계
- 목적 대응표는 사람이 정했다. 표에 없는 소분류(부동산·의료·미용·액세서리 등)는 목적 빈칸이다. PATH-v0 표를 따라 제과점(빵·떡)은 **식사**, 요가·태권도(스포츠강습)는 **공부**로 간다.
- 프랜차이즈 규칙은 흔한 이름도 잡는다(예: '전주식당', 업종이 다른 같은 이름). 독립 가게 일부가 후보에서 빠진다.
- 상호 유사도는 포함 관계도 같다고 본다('스시' ↔ '스시코리아'). 정밀도는 감사 표본으로 잰다.
- 인허가일자는 지위승계 뒤에도 남아 노포가 과대될 수 있다(`docs/campus/limitations.md`).

## 점포 후보와 도착 시간 v0 (로컬)

`<작업 폴더>/데이터/가공/서울캠/store_candidates_v0.csv`. 실행: `~/.venvs/maximus/bin/python -I scripts/build_store_candidates_v0.py` (점포 테이블 v0 먼저).

| 열 | 설명 |
|---|---|
| group | candidate(의외성 상권 안 후보) / inertia_ref(관성 상권 기준 점포) |
| purpose, area_code, store_id | 목적·상권·점포. 같은 점포가 여러 목적 관성 상권에 들면 목적마다 한 줄 |
| mmr_rank, in_k10, in_k20 | SERP-v0 목적별 MMR 순위(상위 20까지만 있음). 기본은 K=10, 민감도는 K=20과 eligible 전체(빈 순위 포함) |
| t_area | 서울캠 → 상권 대표점(분) |
| t_store | `t_area − walk(하차점→대표점) + walk(하차점→점포)`, walk = 직선 × 1.3 ÷ 시속 4km |
| reach_source | 측정(ODsay 캐시) / 추정(직선 회귀) / 도보 |
| reach_flag | 안정(≤25) / 경계(25~30) / 제외(>30) |
| wait_risk | `seoulcampus_areas_reach_v1.csv` 값(그 파일에 없는 상권은 빈칸) |
| 나머지 | 점포 테이블 v0 열 |

- 측정: 캐시된 ODsay 응답(119곳)의 최단 totalTime. 하차점은 마지막 탑승 구간의 끝 좌표다.
- 추정: 캐시 119곳으로 맞춘 `t = 15.5 + 2.83 × 직선km`(잔차 MAE 3.8분, 캐시 범위 직선 약 1~12km). 하차점은 대표점에서 가장 가까운 버스 정류소(`data/raw/서울시버스노선별정류소정보_20260902.xlsx`)나 지하철역(`seoul_station_master_20260902.csv`)이다. 이 두 파일은 `scripts/build_seoul_transit_network.py`가 쓰는 원천이다.
- 직선 1km 안 상권은 걷는 쪽이 더 빠르면 도보로 본다.
- ODsay는 새로 부르지 않는다.

### 한계
- **출발점이 다르다.** 상권 순위(SERP-v0)는 동대문구 정류장·역 334곳의 30분 도달률로 정한다. 점포 시간은 서울캠 한 점에서 잰다. PATH-v0 도달률은 상권 단위 비율이라 점포 보정에 쓸 수 없다. 그래서 K=10 후보 2,132곳 중 73.5%가 서울캠 기준으로 30분을 넘는다(`제외`).
- 추정 상권(K=10 상권 35곳 중 31곳)은 직선거리 회귀라 노선 사정을 모른다.
- 상권 대표점 하나에 하차점 하나를 둔다. 큰 상권(잠실 관광특구)은 가장자리 점포가 최대 44분까지 늘어난다. 이런 점포는 전체의 0.2%다.

## 매칭 감사 표본

`match_audit_sample_v0.csv`: 인허가가 매칭된 상가정보 점포 50곳(무작위, seed 42). 좌표는 없다.
열: 상호, 소분류명, 인허가 상호, 인허가 연도, 거리_m, 판정. **판정 칸은 사람이 채운다**(맞음 / 틀림 / 애매).

## 네이버 장소 연결·키워드 집계 v0 (로컬)

`scripts/naver/match_naver_places_v0.py` → `collect_naver_keyword_reviews_v0.py` 순서로 돌린다. 대상은 식사·카페·공부 K=10 후보와 관성 기준 점포를 합친 3,252곳이다.

- 장소 연결: `map.naver.com/p/api/search/instant-search`(검색어 = 정규화 상호 + 도로명, coords = 점포 좌표). 80m 안이고 상호가 비슷하면 exact, 80m 안이기만 하면 fuzzy, 없으면 none.
- 키워드 집계: `pcmap-api.place.naver.com/graphql`의 `getVisitorReviewStats`. 키워드 코드·문구·선택 인원, 참여 인원(`userCount`), 방문자 리뷰 수만 저장한다. 별점·메뉴·리뷰 본문은 저장하지 않는다. 블로그 리뷰 수는 이 응답에 없다.
- 요청: 쿠키·캡차 토큰을 보내지 않는다. 단일 스레드로 2~3초 + 무작위 지연을 두고, 403·429·캡차 응답이 3번 연속이면 멈춘다. 캐시(`데이터/캐시/naver_search`, `naver_place`)가 있는 곳은 건너뛴다.
- 결과 CSV, 캐시, place_id는 커밋하지 않는다. 공개 파일은 `naver_match_audit_sample_v0.csv`(place_id·좌표 없음)뿐이다.
