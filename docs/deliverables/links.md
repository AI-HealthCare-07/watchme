# 링크

| 항목 | 주소 | 비고 |
|---|---|---|
| 배포 사이트 | https://evrd.fyi | 집 노트북 서버(Ubuntu Server + Docker Compose), Caddy 자동 HTTPS, Porkbun DDNS |
| 헬스 체크 | https://evrd.fyi/healthz | `{"ok": true}` |
| GitHub 저장소 (제출용, 공개) | https://github.com/AI-HealthCare-07/watchme | 개발 저장소의 사본. 작성자 이메일·집 네트워크 정보만 가리고 커밋 이력은 그대로(커밋 번호는 원본과 달라요) |
| GitHub 원본 (개발용, 비공개) | https://github.com/ynofire/watchme | 제출물에 적힌 커밋 번호는 이 저장소 기준 |
| 운영 지표 | https://evrd.fyi/admin | 관리자만(`ADMIN_KEY` 쿠키). 발표 때 카톡 연결자 수 캡처용 |

## 문서

| 문서 | 위치 |
|---|---|
| 설계(원래) | `docs/superpowers/specs/2026-11-13-watchme-design.md` |
| 1단계 개편 설계 | `docs/superpowers/specs/2026-11-16-watchme-redesign-design.md` |
| 2단계 설계 | `docs/superpowers/specs/2026-11-16-watchme-phase2-design.md` |
| 3단계 설계(AI 한 줄 요청) | `docs/superpowers/specs/2026-11-18-watchme-phase3-ai-design.md` |
| 랜딩 개편·대표 아이콘 설계 | `docs/superpowers/specs/2026-11-18-watchme-landing-icon-design.md` |
| 주간 리포트 설계 | `docs/superpowers/specs/2026-11-18-watchme-weekly-report-design.md` |
| 운영 지표 설계 | `docs/superpowers/specs/2026-11-18-watchme-admin-metrics-design.md` |
| 구현 계획 | `docs/superpowers/plans/` (1단계·개편·2단계·3단계·주간 리포트·운영 지표) |
| 서버 운영 기록 | `docs/server-runbook.md` |
| 제출물 | `docs/deliverables/` (이 폴더) |

## 데이터 출처

| 자료 | 용도 |
|---|---|
| 질병관리청 국민건강영양조사(KNHANES) 2022–2024 원시자료 | 성별·연령대별 평균 키·체중, 고혈압·당뇨 유병률, BMI 로지스틱 회귀 계수, 걷기 문항(BE3_31·32·33) 또래 비율 (`scripts/knhanes_stats.py` → `app/data/korea_stats.json`) |
| Google Gemini API (무료 등급) | AI 한 줄 요청: 후보 메뉴·운동 중 뺄 것 고르기 |
| Pretendard / 나눔고딕 (SIL OFL) | 웹 글꼴(자체 호스팅) / PDF 글꼴 |

## 시연 영상

| 항목 | 주소 |
|---|---|
| 시연 영상 | (녹화 후 추가) |
