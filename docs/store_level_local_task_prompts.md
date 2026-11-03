# 점포 단위 추천: 로컬 작업 프롬프트

작성: 2026-11-03 · 설계: `docs/store_level_recommendation_options.md`(안 B + 6장 키워드 리뷰)

로컬 에이전트(Claude Code·Codex)에 **순서대로 하나씩** 넣는다. 각 프롬프트는 앞 단계 결과를 전제한다. 모든 단계에 아래 공통 규칙을 붙인다.

## 공통 규칙 (모든 프롬프트 앞에 붙일 것)

```
[공통 규칙]
- 저장소: maximus-analysis-archive. 기준 브랜치 codex/gunwoo/store-level-recommendation-options. 설계 문서 docs/store_level_recommendation_options.md를 먼저 읽을 것.
- 작업 폴더 구조: <작업 폴더>/데이터/{원천,캐시,가공}. 저장소가 작업 폴더 안에 있으면 자동 탐색, 아니면 MAXIMUS_WORKSPACE=<작업 폴더>.
- 공개 저장소다. 원천 데이터, API 응답 캐시, 네이버 수집 원본·집계, 키를 커밋하지 말 것. 키는 ~/.config/maximus/keys.env 환경변수로만 읽는다.
- 카카오 API 응답(이름·주소·좌표)은 저장해 다시 쓰지 않는다. 좌표는 인허가·상가정보 원본 또는 공공 지오코더(도로명주소 API, 브이월드)만 쓴다.
- 기존 함수 재사용: scripts/campus/모현/build_mohyeon_hidden_stores_v0.py의 norm, is_franchise, similar, KNOWN_CHAINS / scripts/campus/서울캠/build_seoulcampus_area_tags_v1.py의 licenses(), CAFE_TYPES.
- 모형은 규칙 점수·백분위·Ridge·조건부 로짓까지. 딥러닝·SBERT 금지.
- 파일명에 final 금지, 버전은 _v0, _v1. 문서·주석·보고는 한국어.
- 커밋은 코드와 문서만. 형식 feat(store-level): <what> 또는 docs(store-level): <what>. push는 origin, PR은 만들지 말 것.
- 끝나면 실행한 명령, 건수, 막힌 점을 숫자로 보고. 추정과 측정을 구분할 것.
```

---

## P0. 작업 폴더와 원천 재고 확인 (30분)

```
목표: 점포 단위 원천이 로컬 어디에 있는지 확인하고 재고표를 만든다. 코드 수정 없음.

1. 작업 폴더를 찾는다.
   find ~ -maxdepth 6 -type d -name 데이터 2>/dev/null
   mdfind -name seoul_active_20261030
   mdfind -name sbiz_store_info
   ls ~/.config/maximus/keys.env (키 이름만 확인하고 값은 출력하지 말 것)
2. 아래 파일이 있는지, 몇 줄인지 확인한다.
   - 데이터/원천/서울캠/인허가/{general_restaurants,rest_cafes,bakeries}_seoul_active_20261030.csv (기대: 119,974 / 36,957 / 4,316)
   - 데이터/원천/서울캠/착한가격업소/goodprice_seoul_20261030.csv (기대: 2,210)
   - 데이터/원천/sbiz_store_info_20260630.zip, 그리고 안에 서울 CSV가 있는지(unzip -l)
   - 저장소 data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.geojson
   - 저장소 data/processed/serendipity_ranking/serendipity_ranking_latest.csv, inertia_baselines_top10.csv
3. 결과를 표로 보고한다(경로, 있음/없음, 행 수, 기준일). 없는 것은 P1에서 받는다.
```

## P1. 없는 원천 받기 (0.5~1일, P0에서 빠진 것만)

```
목표: 서울 점포 단위 원천을 공식 경로로 확보한다. 받은 파일은 데이터/원천/서울캠/ 아래에 두고 커밋하지 않는다.

1. 인허가 3종(일반음식점·휴게음식점·제과점): 공공데이터포털 행정안전부 식품 조회서비스 API(apis.data.go.kr/1741000/{general_restaurants,rest_cafes,bakeries}). 서비스키는 DATA_GO_KR_KEY.
   - 글캠 스크립트 scripts/campus/모현/download_restaurant_licenses.py의 호출 방식을 재사용하고, 서울 25개 구 개방자치단체코드로 돌린다.
   - 폐업 포함으로 받는다. 생존 백테스트에 폐업일자가 필요하다.
   - 파일명: {서비스}_seoul_all_YYYYMMDD.csv. 영업 중만 뽑은 _seoul_active_YYYYMMDD.csv도 따로 만든다.
   - 좌표는 EPSG:5174. 빈 좌표 건수를 보고한다.
2. 상가(상권)정보 서울: 공공데이터포털 15083033 파일(시도별 CSV). 브라우저 다운로드가 필요하면 사람에게 요청하고 멈춘다. 받은 뒤 서울 CSV 행 수와 기준 분기를 확인한다.
3. 착한가격업소 서울: 서울 열린데이터광장 OA-1173 CSV(공공누리 1유형). 기존 goodprice.go.kr 엑셀은 대조용으로만 남긴다.
4. 착한가격 좌표: 기존 kakao_geocode_goodprice_seoul_*.csv는 쓰지 않는다. 도로명주소 좌표 API(business.juso.go.kr) 또는 브이월드 지오코더로 다시 만든다. 키가 없으면 발급 절차를 보고하고 멈춘다.
5. docs/campus/ 아래에 seoul_store_raw_sources.md를 만들어 출처, 받은 날, 건수, 이용 조건을 적고 커밋한다. 데이터는 커밋하지 않는다.
```

## P2. 서울 점포 테이블 v0 (1.5일)

```
목표: 서울 공식 상권 786곳 안의 점포 한 줄 = 가게 한 곳 테이블을 만든다.

스크립트: scripts/campus/서울캠/build_seoul_store_table_v0.py
입력: 상가정보 서울, 인허가 3종(영업 중), 착한가격(공공 좌표), 상권 폴리곤 commercial_area_candidates_25pct.geojson
처리:
1. 상가정보 점포에 상권 area_code를 공간결합한다(폴리곤 밖 점포는 제외).
2. 인허가와 80m 안 상호 유사도 0.6(similar)으로 매칭해 license_year, license_service, 위생업태를 붙인다. 여러 개면 가장 오래된 인허가를 쓴다. 상가정보에 없는 인허가 점포는 source=license_only로 추가한다.
3. 프랜차이즈: 지점명 있음, 또는 서울 전체에서 5회 이상 나오는 상호 접두어(is_franchise), 또는 KNOWN_CHAINS.
4. 태그: 노포(≤2005), 10년+(2006~2015), 오래된 카페(CAFE_TYPES·제과점 중 ≤2015), 착한가격(80m·유사도 0.6), 상권 안 소분류 희소도 = 1 − pct(같은 상권 같은 소분류 점포 수).
5. 목적 매핑: PATH-v0와 같은 소분류→목적 표를 쓴다(scripts/build_purpose_features.py 확인). 목적은 식사·카페·쇼핑·여가문화·공부.
출력(로컬): 데이터/가공/서울캠/seoul_store_table_v0.csv. store_id, 상호, 소분류, 목적, area_code, 위경도, 층, license_year, 태그들, franchise, source.
검사:
- seoulcampus_area_tags_v1.csv의 상권별 n_nopo·n_10yr와 다시 센 값을 비교해 차이를 보고한다(같은 정의면 거의 같아야 함).
- 표본 50곳 매칭 정밀도를 사람이 확인할 수 있게 data/processed/store_level/match_audit_sample_v0.csv를 만든다(상호·업종·인허가명·거리만 넣고 좌표는 넣지 않음).
커밋: 스크립트와 README(열 설명)만.
```

## P3. 2단계 후보와 도착 시간 보정 (1.5~2일)

```
목표: SERP-v0 상위 상권 안에서 gate를 통과한 점포 후보와 점포별 도착 시간을 만든다.

스크립트: scripts/build_store_candidates_v0.py
입력: seoul_store_table_v0.csv, data/processed/serendipity_ranking/serendipity_ranking_latest.csv(목적별 eligible·mmr_rank), inertia_baselines_top10.csv, 서울캠 seoulcampus_areas_reach_v1.csv(측정 상권 도착 시간)
처리:
1. 목적별 MMR 상위 K=10 상권(민감도 K=20, 그리고 R ≥ 0.6 전체)의 점포를 고른다.
2. gate: 목적 일치 ∧ 영업 중 ∧ 비프랜차이즈.
3. 도착 시간: t_store = t_area − walk(하차점→상권 대표점) + walk(하차점→점포). walk = 직선 × 1.3 ÷ 4km/h.
   - 하차점은 ODsay 측정 상권은 응답의 마지막 하차 지점(캐시에서 읽기), 미측정 상권은 상권 안·근처 가장 가까운 역·정류장(scripts/build_seoul_transit_network.py 정류장 좌표)이다.
   - reach_flag는 ≤25 안정, 25~30 경계, >30 제외.
   - 동대문구 출발(PATH-v0)과 서울캠 출발 중 어느 쪽 시간을 쓰는지 열로 명시한다.
4. 관성 기준 점포: 관성 Top-K 상권마다 식사·카페 점포를 최대 50곳 무작위로 뽑는다(seed 고정).
출력(로컬): 데이터/가공/서울캠/store_candidates_v0.csv(group = candidate / inertia_ref)
보고: 목적별 후보 수, 상권당 후보 수 분포, 경계·제외 비율.
```

## P4. 네이버 장소 연결과 키워드 리뷰 수집 (2~3일)

```
목표: P3 점포(후보 + 관성 기준, 약 3,000곳)에 네이버 플레이스를 연결하고, 키워드 리뷰 집계만 수집한다. 설계는 docs/store_level_recommendation_options.md 6.1~6.2절.

스크립트: scripts/naver/match_naver_places_v0.py, scripts/naver/collect_naver_keyword_reviews_v0.py
수집 규칙:
- 받는 것: place_id, 키워드 문구, 키워드별 선택 인원, 키워드 참여 인원 합(있으면), 방문자 리뷰 수, 블로그 리뷰 수, 수집 시각.
- 받지 않는 것: 리뷰 본문, 닉네임, 사진, 사용자 ID.
- 장소 페이지에서 브라우저 개발자도구로 키워드 통계가 오는 요청을 찾고, 그 요청만 재현한다. HTML 전체를 긁지 말 것.
- 단일 스레드, 요청 간격 2~3초에 무작위 지연. 429·차단 응답이 오면 지수 백오프하고, 3번 연속이면 멈추고 보고한다. 로그인·우회 기법(프록시 회전, 캡차 우회)은 쓰지 않는다.
- 원본 응답은 데이터/캐시/naver_place/{place_id}.json에 둔다. 재실행하면 캐시에서 이어 받는다.
연결:
1. 검색어는 norm(상호) + 도로명(없으면 법정동).
2. 후보 중 좌표 거리 ≤ 80m ∧ similar(상호) → exact, 거리만 맞으면 fuzzy, 없으면 none.
3. data/processed/store_level/naver_match_audit_sample_v0.csv에 표본 50곳을 남긴다(상호·업종·네이버 장소명·거리. place_id·좌표는 넣지 않음).
출력(로컬): 데이터/가공/서울캠/naver_keyword_counts_v0.csv(store_id, place_id, keyword, count, n_participants, n_visitor_reviews, collected_at)
보고: 연결률(exact/fuzzy/none), 수집 성공률, 참여 인원 중앙값(업종별·노포 여부별), 고유 키워드 수와 목록.
```

## P5. 키워드 → 테마 사전 (0.5일, 사람 검수 포함)

```
목표: P4에서 나온 고유 키워드 전체를 10개 안팎 테마로 묶는 사전을 만든다.

1. 고유 키워드 목록을 빈도와 함께 data/processed/store_level/keyword_theme_map_v0.csv로 낸다. 열: keyword, n_stores, total_count, theme, purpose_hint.
2. 설계 6.3절 테마(맛, 가성비·양, 조용·아늑, 감성·인테리어·뷰, 오래 머물기·공부, 혼자, 대화·모임, 특별함, 서비스·청결, 편의)로 1차 배정하고, 애매한 것은 theme=검토필요로 둔다.
3. 사람 검수를 요청하고 멈춘다. 검수 뒤 확정본을 커밋한다. 키워드 문구는 공개해도 되는 일반 표현이라 커밋 가능하다.
```

## P6. 성격 벡터와 점포 점수 (1~1.5일)

```
목표: 설계 6.4~6.5절대로 가게 성격 벡터와 점포 점수를 만들고 최종 추천 목록을 낸다.

스크립트: scripts/build_store_serendipity_v0.py (+ tests/test_build_store_serendipity_v0.py)
1. 비율 p = c / n, 경험적 베이즈 축소 m = 20(민감도 10·40), 업종(소분류) 평균 μ 대비 lift ℓ = log(p̃/μ), 테마 점수 t = 업종 내 비중 가중 합.
2. n < 20이면 v = 0, review_evidence = low. 제외하지 말 것.
3. fit = 목적별 테마 가중(6.5절 a 표) → 백분위. r_store = 0.4·pct(영업연수|소분류) + 0.2·지정 + 0.4·pct(fit). 근거 부족이면 fit 0.5.
4. u_content = 1 − max_j cos(v_s, 관성 상권 j 평균 벡터). u_local = 상권 평균 벡터와의 거리 백분위.
   u_store = 0.3·희소도 + 0.2·노포/10년+(0.5) + 0.3·u_content + 0.2·u_local.
5. s_store = r_store × u_store. 상권 안 MMR로 3곳(같은 소분류 1곳), 최종 S = S_area × s_store, 목적별 30곳(상권당 최대 3곳).
6. reason: lift ≥ 0.4인 테마 상위 2개 + 공공 태그(노포·착한가격 등)로 한국어 한 줄.
7. 민감도: m, 가중치 ±0.1, K, 인기 감점(u_novelty_store 0.1) 유무. 상위 30 자카드로 보고.
8. 테스트: 축소식, 근거 부족 처리, 상권당 3곳 제한, 프랜차이즈 제외를 작은 고정 데이터로 확인.
출력:
- 로컬: 데이터/가공/서울캠/store_serendipity_v0.csv(전체 열)
- 공개(data/processed/store_level/): store_serendipity_top30_v0.csv. 상호, 소분류, 상권명, 목적, 순위, 테마 태그, 공공 태그, reach_flag, reason만. 키워드 수·place_id·좌표는 넣지 않는다.
```

## P7. 검증과 설문 카드 (1일 + 응답 기간)

```
목표: 설계 4.2·6.6절 검증을 돌리고 설문 카드를 만든다.

1. 테마 안정성: 다항분포 재표집 1,000회로 상위 테마가 유지되는 비율을 n 구간별로 본다.
2. 구성 타당도: 가성비 테마 vs 착한가격 지정 AUC, 혼자 테마 vs 분식·국수 업종, 감성 테마 vs 영업연수 상관.
3. 편향: review_evidence = low 비율을 노포/비노포, 상권 유형별로 비교한다.
4. 기여 분석: 리뷰 특성 있음/없음 순위의 자카드, 관성 겹침, ILD, 테마 커버리지.
5. 설문 카드: 응답자당 20장(의외성 10 + 기준선 10: 상권 안 가까운 순, 상권 안 무작위 비프랜차이즈, 관성 상권 상위). 순서는 무작위, 출처는 숨긴다.
   문항: Q1 아는 곳인가(가 봄/들어 봄/처음), Q2 평소 떠올렸을 곳인가(1~5), Q3 가 보고 싶은가(1~5), Q4 가 본 경우 카드 특징이 맞나(예/아니오).
   구글폼에 넣을 수 있는 CSV로 낸다.
6. 결과를 docs/store_level_validation_v0.md에 숫자로 정리하고 커밋한다.
```
