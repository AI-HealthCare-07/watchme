# Watchme 최종 프로젝트 제출물

OZ코딩스쿨 최종 프로젝트 제출 자료 모음이에요. 코드·설계 문서 기준으로 만들었고, 구현이 진행되면(2단계 카카오 ✅, 3단계 AI ✅) 함께 갱신해요.

| 제출물 | 파일 | 기준 |
|---|---|---|
| ERD | [erd.md](erd.md) | `app/models.py` |
| 요구사항 정의서 | [requirements.md](requirements.md) | `docs/superpowers/specs/` |
| API 명세서 | [api.md](api.md) | `app/routes.py`, `app/kakao_routes.py` |
| 와이어프레임 | [wireframes.md](wireframes.md) | `app/templates/` |
| 링크 | [links.md](links.md) | 배포 주소, GitHub, 문서 |
| PPT 구성안 | [ppt-outline.md](ppt-outline.md) | — |
| 시연영상 대본 | [demo-script.md](demo-script.md) | — |
| README 목차 | [readme-outline.md](readme-outline.md) | — |

## 2단계 진행 상황 (✅ 완료, 2026-11-17 운영 반영)

| 2단계 계획 Task | 상태 | 갱신할 제출물 |
|---|---|---|
| 1·2 설정·카카오 HTTP 클라이언트 | ✅ | — |
| 3 새 표(`kakao_accounts`·`trial_owners`·`sent_messages`·`next_trials`) | ✅ | erd |
| 4 로그인 경로·환영 메시지·연결 카드 | ✅ | api, wireframes, requirements |
| 5 첫 배포·실험(알림 울리는지) | ✅ | demo-script, wireframes(메시지 문구) |
| 6 아침·저녁 발송 | ✅ | api(cron), requirements |
| 7 알림 끄기·연결 끊기 | ✅ | api, wireframes |
| 8 다음 30일 도전 | ✅ | api, wireframes, erd |
| 9 보관 삭제 확장·개인정보 안내 | ✅ | requirements, wireframes |
| 10 최종 배포·cron | ✅ | ppt-outline, links |

- 11/18 화면 개편(기록 화면 맨 위 카톡 바·칩·접는 위험도·주황 지난 날 띠, 시작·결과 화면 축약, 항상 밝은 화면)도 반영했어요.

## 3단계 진행 상황 (AI 한 줄 요청, ✅ 완료, 2026-11-18 운영 반영)

| 3단계 계획 Task | 상태 | 갱신할 제출물 |
|---|---|---|
| 2 Gemini 클라이언트(`app/ai.py`) | ✅ | — |
| 3 새 표 `ai_picks`·계획에 제외 반영 | ✅ | erd |
| 4 설정 화면 한 줄 요청·AI 호출 | ✅ | api, wireframes, requirements |
| 5 준비·기록 화면 안내·개인정보 문구·다음 도전 복사 | ✅ | wireframes, requirements |
| 6 runbook·배포·첫 실험 | ✅ | links, demo-script, ppt-outline |

- 랜딩 스토리형 개편·대표 아이콘(2026-11-18): wireframes ①, requirements FR-01·FR-01a 반영.
- 마지막 갱신: 2026-11-18 (기준 커밋 `998b58d`, landing 브랜치, 테스트 285개 통과, 배포 전)
