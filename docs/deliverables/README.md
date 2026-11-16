# Watchme 최종 프로젝트 제출물

OZ코딩스쿨 최종 프로젝트 제출 자료 모음이에요. 코드·설계 문서 기준으로 만들었고, 2단계(카카오) 구현이 진행되면 함께 갱신해요.

| 제출물 | 파일 | 기준 |
|---|---|---|
| ERD | [erd.md](erd.md) | `app/models.py` (+ 2단계 예정 표 따로) |
| 요구사항 정의서 | [requirements.md](requirements.md) | `docs/superpowers/specs/` |
| API 명세서 | [api.md](api.md) | `app/routes.py` |
| 와이어프레임 | [wireframes.md](wireframes.md) | `app/templates/` |
| 링크 | [links.md](links.md) | 배포 주소, GitHub, 문서 |
| PPT 구성안 | [ppt-outline.md](ppt-outline.md) | — |
| 시연영상 대본 | [demo-script.md](demo-script.md) | — |
| README 목차 | [readme-outline.md](readme-outline.md) | — |

## 2단계 진행 상황 (갱신할 때마다 고쳐요)

| 2단계 계획 Task | 상태 | 갱신할 제출물 |
|---|---|---|
| 1·2 설정·카카오 HTTP 클라이언트 | 구현 전 | — |
| 3 새 표(`kakao_accounts`·`trial_owners`·`sent_messages`·`next_trials`) | 구현 전 | erd |
| 4 로그인 경로·환영 메시지·연결 카드 | 구현 전 | api, wireframes, requirements |
| 5 첫 배포·실험(알림 울리는지) | 구현 전 | demo-script, wireframes(메시지 문구) |
| 6 아침·저녁 발송 | 구현 전 | api(cron), requirements |
| 7 알림 끄기·연결 끊기 | 구현 전 | api, wireframes |
| 8 다음 30일 도전 | 구현 전 | api, wireframes, erd |
| 9 보관 삭제 확장·개인정보 안내 | 구현 전 | requirements, wireframes |
| 10 최종 배포·cron | 구현 전 | ppt-outline, links |

- 마지막 갱신: 2026-11-16 (기준 커밋 `c031f61`, 테스트 152개 통과)
