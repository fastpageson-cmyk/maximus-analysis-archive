# 의외성 재순위화 SERP-v0 결과

생성: `python3 scripts/build_serendipity_ranking.py` / 설계·해석: `docs/serendipity/recommendation_design.md`

저장소 안 공개 가공 데이터만 쓴다(API 호출 없음, B078/B079 원본 없음).

| 파일 | 내용 |
|---|---|
| `serendipity_ranking_latest.csv` | 20254 분기, 786곳 × 5목적 전체 점수(R, U 성분, S, 하한 통과, MMR 순위, 근거) |
| `serendipity_top10_by_purpose.csv` | 목적별 MMR 상위 10 |
| `inertia_baselines_top10.csv` | 관성 기준선(거리순·인기순·과거 유입순) 목적별 상위 10 |
| `serendipity_beyond_accuracy.csv` | 겹침률·커버리지·ILD·지니 등 |
| `serendipity_backtest_proxy_label.csv` | 20252→20254 사후 프록시 라벨 백테스트 |
| `serendipity_sensitivity.csv` | R 하한·λ·U 가중치·K 민감도 |
| `serendipity_counterfactual.csv` | 유입 일부가 추천으로 옮겨갈 때 도시 지니 변화 |
| `run_summary.json` | 설정값, 목적별 하한 통과 수 |

주의: `observed_inflow`는 동대문구발 OD가 아니라 생활이동(2026-08) 모든 출발지 비일상 유입 × 동대문구 30분 도달률 프록시다. 생활이동 유입은 행정동 단위 배분값이다.
