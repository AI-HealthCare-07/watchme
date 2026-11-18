# 링크

| 항목 | 주소 | 비고 |
|---|---|---|
| 배포 사이트 | https://evrd.fyi | 집 노트북 서버(Ubuntu Server + Docker Compose), Caddy 자동 HTTPS, Porkbun DDNS |
| 헬스 체크 | https://evrd.fyi/healthz | `{"ok": true}` |
| GitHub 저장소 | https://github.com/ynofire/watchme | ⚠️ 2026-11-16 확인 기준 **비공개(PRIVATE)** — 심사자가 보려면 공개로 바꾸거나 협업자로 초대해야 해요 |

## 문서

| 문서 | 위치 |
|---|---|
| 설계(원래) | `docs/superpowers/specs/2026-11-13-watchme-design.md` |
| 1단계 개편 설계 | `docs/superpowers/specs/2026-11-16-watchme-redesign-design.md` |
| 2단계 설계 | `docs/superpowers/specs/2026-11-16-watchme-phase2-design.md` |
| 3단계 설계(AI 한 줄 요청) | `docs/superpowers/specs/2026-11-18-watchme-phase3-ai-design.md` |
| 구현 계획 | `docs/superpowers/plans/` (1단계·개편·2단계·3단계) |
| 서버 운영 기록 | `docs/server-runbook.md` |
| 제출물 | `docs/deliverables/` (이 폴더) |

## 데이터 출처

| 자료 | 용도 |
|---|---|
| 질병관리청 국민건강영양조사(KNHANES) 2022–2024 원시자료 | 성별·연령대별 평균 키·체중, 고혈압·당뇨 유병률, BMI 로지스틱 회귀 계수 (`scripts/knhanes_stats.py` → `app/data/korea_stats.json`) |
| Pretendard / 나눔고딕 (SIL OFL) | 웹 글꼴(자체 호스팅) / PDF 글꼴 |

## 시연 영상

| 항목 | 주소 |
|---|---|
| 시연 영상 | (녹화 후 추가) |
