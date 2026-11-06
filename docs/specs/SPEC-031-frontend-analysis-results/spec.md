---
id: SPEC-031
title: 분석 결과 화면(이벤트 타임라인·위험 상태·요약)과 실시간 알림
status: Approved
owner: <이름>
repos: [frontend, docs]
created: 2026-11-06
updated: 2026-11-06
related: [SPEC-001, SPEC-002, SPEC-005, SPEC-006, SPEC-027, SPEC-028]
---

# SPEC-031 분석 결과 화면(이벤트 타임라인·위험 상태·요약)과 실시간 알림

> 이 문서에는 **무엇을, 왜**만 쓴다. 클래스, 테이블, 라이브러리 같은 구현 방법은 각 레포의 plan.md에 쓴다.

## 1. 배경과 목적

지금 영상 상세 화면(SPEC-006)은 원본 재생만 한다. 분석이 끝나도 사용자는 무엇이 언제 일어났는지 볼 수 없다. [아키텍처 v5](../../architecture/architecture.md) 처리 흐름 12단계는 다음을 정한다.

- 플레이어에서 이벤트를 누르면 시작 2초 전으로 이동한다.
- 위험 상태 패널은 활성 위험과 해소 이력을 보여 준다.
- 진행률과 완료는 SSE로 받는다.

이 spec은 영상 상세 화면에 다음을 채운다.

- 분석 요약, 이벤트 타임라인·상세, 운영자 확인·기각
- 위험 상태(노출 지표·참고용 예측), 상태 스냅샷, 판정하지 않은 이벤트 유형
- 사이드바 "이벤트" 메뉴의 전체 이벤트 목록
- 앱 전체가 함께 쓰는 실시간 알림 연결

화면이 쓰는 analysis-api 공개 API와 notification-service SSE는 다른 담당자 서비스다. 계약이 없어 이 spec이 아키텍처 문서 "외부 API" 표대로 먼저 정한다(생산자 확인 필요, [handoff](../../handoff.md) 2.1).

## 2. 범위

### 포함

- 계약
  - `openapi/analysis-service.yaml` 0.3.0 공개 API 7개: 영상 이벤트 목록, 내 이벤트 목록, 이벤트 상세, 확인·기각, 위험 상태, 스냅샷, 요약(생산자 확인 필요)
  - `openapi/notification-service.yaml` 0.1.0 SSE 구독과 메시지 형식 `notifications/v1/notification-message`(생산자 확인 필요)
- 영상 상세 화면
  - 분석 요약 패널, 이벤트 타임라인(플레이어 진행 막대 표시와 목록·거르기)
  - 이벤트 상세(근거 프레임, 판정 결과, 조치 제안, 판정 방식), 운영자 확인·기각
  - 위험 상태 패널(활성·해소, 노출 지표, 예측은 "참고용"), 상태 스냅샷, 판정하지 않은 이벤트 유형, 작업 세션 표시
  - 분석 진행률
- "이벤트" 메뉴: 내 영상 전체의 이벤트 목록과 거르기, 영상 상세로 이동
- 실시간 알림: 티켓 발급, 연결 하나 공유, 재연결, `Last-Event-ID` 이어 받기, 로그아웃 시 끊기

### 제외

- 클릭 조회·오버레이·객체 질문·위험구역 편집: SPEC-032
- 검색·RAG: SPEC-033
- 재분석 요청, 활성 버전 전환 화면: 운영자 기능이고 pipeline-service·analysis-api 담당자와 함께 정한다(이후 spec).
- 브라우저 알림(Notification API)과 소리 알림

## 3. 사용자 시나리오

### US-1 분석 결과 훑어보기 (P1)

안전관리자로서 영상을 열면 요약과 이벤트 목록을 먼저 보고, 이벤트를 누르면 그 장면을 바로 보고 싶다. 왜냐하면 긴 영상을 처음부터 볼 시간이 없기 때문이다.

#### 인수 조건

- Given 분석이 끝난 영상, When 영상 상세를 열면, Then 요약문, 이벤트 수, 활성 위험 수가 보이고 플레이어 진행 막대에 이벤트 위치가 표시된다.
- Given 이벤트 목록, When 이벤트를 누르면, Then 플레이어가 시작 2초 전(`seekMs`)으로 이동하고 이벤트 상세가 열린다.
- Given 판정 결과가 `unverified`·`unknown`인 이벤트, When 목록을 보면, Then 각각 "미확인(모델 없음)"·"판단 불가"로 표시되고 설명 자리에 그 사실이 보인다.

### US-2 위험 상태 보기 (P1)

안전관리자로서 영상 끝까지 해소되지 않은 위험과, 그 위험에 몇 명이 얼마나 노출됐는지 보고 싶다.

#### 인수 조건

- Given 활성 위험 하나와 해소 위험 하나, When 위험 패널을 보면, Then 활성이 위에, 해소가 아래에 보이고 각각 구역, 유형, 사유, 시작·해소 시각, 노출 인원·시간이 보인다.
- Given 예측 결과가 있는 활성 위험, When 패널을 보면, Then 예측이 "참고용" 표시와 함께 보인다.

### US-3 분석 진행 보기 (P1)

사용자로서 영상을 올린 뒤 분석이 얼마나 진행됐는지 새로고침 없이 보고 싶다.

#### 인수 조건

- Given 분석 중인 영상의 상세 화면, When 진행 알림이 오면, Then 진행률이 갱신된다.
- Given 분석 완료 알림(`source.completed`), When 받으면, Then 요약·이벤트·위험이 다시 불러와진다.
- Given 네트워크가 끊겼다 돌아옴, When 다시 연결하면, Then 끊긴 동안의 알림을 이어 받는다.

### US-4 이벤트 확인·기각 (P2)

운영자로서 잘못된 이벤트를 기각하고 맞는 이벤트를 확인해 두고 싶다.

#### 인수 조건

- Given OPERATOR 역할, When 이벤트 상세에서 "기각"과 메모를 저장하면, Then 목록의 그 이벤트가 "기각"으로 바뀐다.
- Given USER 역할, When 이벤트 상세를 보면, Then 확인·기각 버튼이 보이지 않는다.

### US-5 전체 이벤트 보기 (P2)

안전관리자로서 여러 영상의 high 이벤트를 한곳에서 보고 싶다.

#### 인수 조건

- Given "이벤트" 메뉴, When severity high로 거르면, Then 내 영상 전체의 high 이벤트가 최신순으로 보이고, 누르면 그 영상 상세가 이벤트 시각으로 열린다.

## 4. 요구사항

### 기능 요구사항 (EARS)

| ID | 요구사항 | 시나리오 |
| --- | --- | --- |
| R-1 | WHEN 사용자가 영상 상세를 열면, THE frontend SHALL 그 영상의 요약을 불러와 `status`가 `NOT_ANALYZED`이면 "아직 분석 결과가 없음" 안내를, `READY`이면 요약 패널과 결과 패널을 표시한다. | US-1 |
| R-2 | THE frontend SHALL 요약 패널에 요약문(요약 상태가 `generated`가 아니면 상태별 안내), 이벤트·확정 이벤트·활성 위험 수, 판정하지 않은 이벤트 유형과 이유, 작업 세션 역할과 직전 영상 상태 사용 여부를 표시한다. | US-1 |
| R-3 | THE frontend SHALL 이벤트 목록을 시작 시각 순으로 표시하고 유형·severity·판정 상태·확인 상태로 거를 수 있게 하며, 이벤트마다 유형, 시각, severity, 판정 상태, 설명 첫 줄, 썸네일을 표시한다. | US-1 |
| R-4 | THE frontend SHALL 플레이어 진행 막대 위에 이벤트 시작 위치를 severity별 색으로 표시하고, 표시를 누르면 R-5와 같이 동작한다. | US-1 |
| R-5 | WHEN 사용자가 이벤트를 누르면, THE frontend SHALL 플레이어를 그 이벤트의 `seekMs`로 옮기고 이벤트 상세(근거 프레임, 설명, 위험 사유, "안전관리자 확인 필요" 표시와 조치 제안, 판정 방식, 판정 호출 요약)를 연다. | US-1 |
| R-6 | THE frontend SHALL 판정 상태 `confirmed`·`rejected`·`unverified`·`unknown`을 "확인됨"·"이벤트 아님"·"미확인(모델 없음)"·"판단 불가"로 표시하고, 설명이 null이면 그 상태의 안내 문구를 대신 표시한다. | US-1 |
| R-7 | WHERE 사용자 역할에 OPERATOR가 있으면, THE frontend SHALL 이벤트 상세에 확인·기각·되돌리기와 메모 입력을 표시하고, 저장하면 확인 상태를 바꿔 목록과 상세를 갱신한다. | US-4 |
| R-8 | THE frontend SHALL 위험 패널에 활성 위험을 먼저, 해소 위험을 다음에 표시하고 위험마다 구역 이름(없으면 "전체"), 유형, 사유, 시작·해소 시각, 노출 인원, 노출 시간, 세션에서 이어 온 위험 표시를 보여 주며, 시작 시각을 누르면 플레이어를 그 시각으로 옮긴다. | US-2 |
| R-9 | WHERE 위험에 예측 결과가 있으면, THE frontend SHALL 예측 구간별 노출 확률을 "참고용" 표시와 함께 보여 주고, 예측이 없으면 그 자리를 비운다. | US-2 |
| R-10 | THE frontend SHALL 상태 스냅샷을 시각 순으로 구역별 이전 상태 → 현재 상태로 표시하고, 관련 이벤트를 누르면 R-5와 같이 동작한다. | US-2 |
| R-11 | WHEN 사용자가 "이벤트" 메뉴에 들어오면, THE frontend SHALL 내 영상 전체의 이벤트를 최신순으로 쪽 나눠 표시하고 유형·severity·판정 상태·확인 상태·기간으로 거를 수 있게 하며, 이벤트를 누르면 그 영상 상세를 그 이벤트가 열린 상태로 연다. | US-5 |
| R-12 | WHILE 사용자가 로그인해 있으면, THE frontend SHALL SSE 티켓을 받아 알림 스트림에 연결 하나를 열어 두고 모든 화면이 그 연결을 함께 쓴다. | US-3 |
| R-13 | IF 알림 연결이 끊기면, THEN THE frontend SHALL 1초부터 두 배씩 최대 30초까지 늘려 기다린 뒤 새 티켓으로 다시 연결하고, 마지막으로 받은 이벤트 id를 `Last-Event-ID`로 보낸다. | US-3 |
| R-14 | WHEN 사용자가 로그아웃하면, THE frontend SHALL 알림 연결을 닫고 재연결하지 않는다. | US-3 |
| R-15 | WHEN 열린 영상 상세의 `job.status` 알림이 오면, THE frontend SHALL 분석 진행률과 상태를 갱신하고, 끝난 상태(`terminal`)이면 진행 표시를 닫는다. | US-3 |
| R-16 | WHEN 열린 영상의 `source.completed` 알림이 오면, THE frontend SHALL 요약·이벤트·위험·스냅샷을 다시 불러온다. | US-3 |
| R-17 | IF 분석 API가 404를 돌려주면, THEN THE frontend SHALL 영상을 찾을 수 없다는 안내를 표시하고, 5xx·네트워크 오류면 다시 시도 버튼과 함께 오류 안내를 표시한다. | US-1 |
| R-18 | THE frontend SHALL 이벤트 목록과 위험 패널을 키보드만으로 이동·선택할 수 있게 하고, severity를 색과 글자로 함께 표시한다. | US-1 |

### 비기능 요구사항

| ID | 요구사항 |
| --- | --- |
| NFR-1 | THE frontend SHALL 이벤트 500개인 영상 상세에서 목록·진행 막대 표시를 로컬 기준 첫 응답 뒤 300ms 안에 그린다. |
| NFR-2 | THE frontend SHALL 화면을 여러 개 열어도 알림 연결을 탭당 하나만 연다. |
| NFR-3 | THE frontend SHALL 서명 주소와 SSE 티켓을 로그·브라우저 저장소에 남기지 않는다. |

## 5. 영향 범위

| 레포 / 서비스 | 변경 개요 | 담당 요구사항 |
| --- | --- | --- |
| frontend / features/analysis | 요약·이벤트·상세·위험·스냅샷 패널, 진행 막대 표시, 이벤트 메뉴 화면 | R-1~R-11, R-15~R-18, NFR-1 |
| frontend / features/notifications | SSE 연결 공유, 재연결, 이어 받기, 로그아웃 처리 | R-12~R-14, NFR-2, NFR-3 |
| frontend / api/generated | analysis-service·notification 계약에서 생성한 타입 | R-1~R-16 |
| docs | 계약 | R-1~R-16 |
| backend / analysis-api·notification-service (다른 담당자) | (이후) 공개 API·SSE 구현 | — |

## 6. 계약 변경

| 계약 파일 | 변경 | 하위호환 |
| --- | --- | --- |
| `service-contracts/openapi/analysis-service.yaml` | 공개 API 7개, bearer 보안 기본값(내부 API는 `security: []` 유지), 0.2.0 → 0.3.0(생산자 확인 필요) | 예(추가) |
| `service-contracts/openapi/notification-service.yaml` | 새 파일: SSE 구독(0.1.0, 생산자 확인 필요) | 예(추가) |
| `service-contracts/notifications/v1/notification-message.schema.json` | 새 메시지 형식 | 예(추가) |

계약 묶음 3.10.0 → 3.11.0

## 7. 성공 지표

- 계약 예시로 응답하는 mock 서버로 영상 상세의 요약·이벤트·위험·스냅샷과 이벤트 메뉴가 모두 그려지고, mock SSE의 진행·완료 알림에 화면이 갱신된다.

## 8. 미결 사항

- 해당 없음
