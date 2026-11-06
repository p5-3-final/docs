---
id: SPEC-035
title: 품질 화면(검토 큐·Golden Set·평가 실행·처리 단계·데이터셋 가져오기)
status: Approved
owner: <이름>
repos: [frontend, backend, docs]
created: 2026-11-06
updated: 2026-11-06
related: [SPEC-002, SPEC-029, SPEC-030, SPEC-031, ADR-0016]
---

# SPEC-035 품질 화면(검토 큐·Golden Set·평가 실행·처리 단계·데이터셋 가져오기)

> 이 문서에는 **무엇을, 왜**만 쓴다. 클래스, 테이블, 라이브러리 같은 구현 방법은 각 레포의 plan.md에 쓴다.

## 1. 배경과 목적

quality-service(SPEC-029·SPEC-030)는 검토 큐, Golden Set, 평가 실행, 처리 단계 리포트, 데이터셋 가져오기, 특징 내보내기 API를 운영자(OPERATOR)에게 준다. 운영자가 이 API를 화면 없이 쓰면 다음 문제가 생긴다.

- 근거 프레임을 보며 라벨을 붙이기 어렵다.
- Gate 실패 원인과 단계별 지연 추이를 한눈에 볼 수 없다.

이 spec은 OPERATOR에게만 보이는 사이드바 "품질" 메뉴와 하위 화면 다섯 개를 만든다. 계약은 SPEC-029·SPEC-030의 `openapi/quality-service.yaml`을 쓴다. 근거 프레임을 화면에 띄우도록 검토 항목 응답에 서명 주소 필드만 더한다.

v5.1([아키텍처 v5.1](../../architecture/architecture.md) 16절): 검토 큐 사유 필터와 긴급 알림 지표를 더한다.

## 2. 범위

### 포함

- 사이드바 "품질" 메뉴(OPERATOR만). 하위 탭: 검토 큐, Golden Set, 평가 실행, 처리 단계, 데이터셋
- 검토 큐: 상태·사유·유형 거르기 목록, 항목 맡기·내려놓기, 상세(근거 프레임, 판정 결과, 판정 이유), 라벨 입력·저장, 다음 항목으로
- Golden Set: 목록·만들기, 상세(초안 항목·확정 버전·기준 실행), 초안에 검토 항목 넣기·빼기, 버전 확정, 기준 실행 지정, 매니페스트 경로 표시
- 평가 실행: 목록(Golden Set 거르기), 상세(버전, 지표 표, Gate 결과와 실패 지표 강조)
- 처리 단계: 영상 ID로 단계 분해 표, 단계·기간·버전으로 일별 p50·p95 추이 그래프
- 데이터셋: 가져오기 시작(매니페스트 경로·평가 비율·분할 시드), 가져오기 목록·진행 상태·오류, 특징 내보내기 시작과 상태·파일 경로

### 제외

- 평가 잡 실행 버튼: 평가 잡은 CI·운영자 명령으로 돌린다(SPEC-030 R-19).
- 내보낸 특징 파일 내려받기: 파일 경로만 보여 준다. 내려받기 주소 발급은 이후 spec이다.
- bbox·상태 변화 라벨을 그리는 도구: SPEC-030 제외 항목과 같다.

## 3. 사용자 시나리오

### US-1 검토 큐 처리 (P1)

운영자로서 큐에서 항목을 맡아 근거 프레임을 보고 라벨을 붙인 뒤 다음 항목으로 바로 넘어가고 싶다. 왜냐하면 검토 항목이 많아서 화면을 오가며 일하면 시간이 많이 들기 때문이다.

#### 인수 조건

- Given `UNASSIGNED` 항목, When "맡기"를 누르면, Then 상세가 열리고 라벨 입력이 활성화된다. 다른 사람이 먼저 맡았으면(409) "이미 다른 사람이 맡음"이 보이고 목록이 갱신된다.
- Given 맡은 항목, When verdict·이벤트 유무·유형·구간·메모를 넣고 "저장 후 다음"을 누르면, Then 저장되고 다음 `UNASSIGNED` 항목 맡기가 이어진다.
- Given `eventPresent`를 켰는데 구간이 비었음, When 저장하려 하면, Then 저장 버튼이 막히고 이유가 보인다.

### US-2 Golden Set 버전 확정 (P1)

운영자로서 라벨 항목을 Golden Set 초안에 모아 버전으로 확정하고 기준 실행을 정하고 싶다.

#### 인수 조건

- Given 라벨된 검토 항목, When "Golden Set에 넣기"로 세트를 고르면, Then 그 세트 초안에 들어간다. uncertain이거나 이미 들어 있으면 이유가 보인다.
- Given 초안 항목 3개, When "버전 확정"을 누르고 확인하면, Then 새 버전 번호와 매니페스트 경로가 보이고 초안 수가 0이 된다.

### US-3 Gate 실패 원인 보기 (P1)

개발자로서 CI Gate가 실패한 평가 실행에서 어떤 지표가 얼마나 떨어졌는지 보고 싶다.

#### 인수 조건

- Given `passed: false` 실행, When 상세를 열면, Then 실패 지표가 기준값·실행값·차이와 함께 강조되어 맨 위에 보인다.
- Given 기준 실행이 없는 실행, When 상세를 열면, Then "기준 실행 없음"이 보인다.

### US-4 처리 단계 지연 보기 (P2)

운영자로서 특정 영상이 어느 단계에서 오래 걸렸는지, 판정 단계 p95가 모델 버전마다 어떻게 바뀌는지 보고 싶다.

#### 인수 조건

- Given 영상 ID, When 단계 분해를 조회하면, Then 단계 경로별 개수·합계·p50·p95·오류 수가 합계 내림차순으로 보인다.
- Given 단계 `analyzer.judge`, 기간 7일, 버전 키 `modelId`, When 추이를 조회하면, Then 날짜별 p50·p95 선 그래프와 표가 보인다.

### US-5 데이터셋 가져오기 (P2)

AI 담당자로서 가져오기 버킷에 올린 매니페스트를 화면에서 가져오고 진행 상황을 보고 싶다.

#### 인수 조건

- Given 매니페스트 경로, When 가져오기를 시작하면, Then 목록에 `PENDING`으로 나오고 상태가 끝날 때까지 갱신된다.
- Given 일부 영상이 실패한 가져오기, When 상세를 보면, Then 개수와 오류 목록, 만든 Golden Set 버전이 보인다.

## 4. 요구사항

### 기능 요구사항 (EARS)

| ID | 요구사항 | 시나리오 |
| --- | --- | --- |
| R-1 | WHERE 사용자 역할에 OPERATOR가 있으면, THE frontend SHALL 사이드바에 "품질" 메뉴를 표시하고, 없으면 메뉴를 숨기며 품질 경로로 직접 들어오면 권한 없음 안내를 표시한다. | US-1 |
| R-2 | THE frontend SHALL 검토 큐 목록을 상태·사유·유형으로 거르고 만든 순서로 쪽 나눠 표시하며, 항목마다 유형, 구간, 판정 방식, 사유, 상태, 맡은 사람(나인지 표시)을 보여 준다. | US-1 |
| R-3 | WHEN 운영자가 "맡기"를 누르면, THE frontend SHALL 맡기를 요청하고 성공하면 상세를 연다. 409이면 "이미 다른 사람이 맡음"(라벨이 끝난 항목은 "이미 라벨됨")을 표시하고 목록을 다시 불러온다. | US-1 |
| R-4 | THE frontend SHALL 검토 상세에 근거 프레임(응답의 `evidenceFrameUrls` 서명 주소), 판정 결과(설명·위험 사유·severity·판정 상태), 판정 방식, 판정 이유(`reviewReasons`)를 표시하고, 서명 주소가 만료돼 이미지를 못 읽으면 상세를 다시 불러온다. | US-1 |
| R-5 | THE frontend SHALL 라벨 입력(verdict, 이벤트 유무, 유형, 시작·끝 시각, severity, 메모 500자)을 맡은 사람에게만 활성화하고, 이벤트 유무가 켜지면 유형·시작·끝을 필수로, 끝 > 시작을 요구하며, 꺼지면 유형을 비운다. | US-1 |
| R-6 | WHEN 운영자가 "저장 후 다음"을 누르면, THE frontend SHALL 라벨을 저장하고, 성공하면 같은 거르기 조건의 다음 `UNASSIGNED` 항목을 맡아 연다. 다음 항목이 없으면 "남은 항목 없음"을 표시한다. | US-1 |
| R-7 | WHEN 운영자가 맡은 항목에서 "내려놓기"를 누르면, THE frontend SHALL 내려놓기를 요청하고 목록으로 돌아간다. | US-1 |
| R-8 | THE frontend SHALL Golden Set 목록에 이름·분할·출처(검토·가져오기)·초안 수·최신 버전·기준 실행을 표시하고, 이름(소문자·숫자·하이픈)·분할·설명으로 만들기를 제공한다. | US-2 |
| R-9 | WHEN 운영자가 라벨된 검토 항목 상세에서 "Golden Set에 넣기"로 출처가 검토인 세트를 고르면, THE frontend SHALL 초안 넣기를 요청하고, 409이면 이유(라벨 없음·uncertain·이미 들어 있음·가져온 데이터셋 세트)를 표시한다. | US-2 |
| R-10 | THE frontend SHALL Golden Set 상세에 초안 항목 목록(빼기 포함), 확정 버전 목록(버전·항목 수·매니페스트 경로·확정 시각·확정한 사람), "버전 확정" 버튼을 표시하고, 확정은 확인 창 뒤에 요청하며 409이면 이유(초안 없음·확정 진행 중)를 표시한다. | US-2 |
| R-11 | WHEN 운영자가 평가 실행 상세에서 "기준으로 지정"을 누르면, THE frontend SHALL 그 실행의 Golden Set 기준 실행을 바꾸고, 409이면 다른 세트의 실행이라는 안내를 표시한다. | US-3 |
| R-12 | THE frontend SHALL 평가 실행 목록을 받은 시각 내림차순으로 Golden Set·버전·종류·트리거·Gate 결과(통과·실패·기준 없음)와 함께 표시하고, Golden Set으로 거를 수 있게 한다. | US-3 |
| R-13 | THE frontend SHALL 평가 실행 상세에 버전 정보, Gate 결과, 실패 지표(이름·유형·기준값·실행값·차이)를 맨 위에 강조해 표시하고, 그 아래 전체 지표를 이름·유형 순 표로 표시한다. | US-3 |
| R-14 | WHEN 운영자가 영상 ID로 단계 분해를 조회하면, THE frontend SHALL 단계 경로별 개수·합계·p50·p95·오류 수를 합계 내림차순 표로 표시하고, 404이면 "측정 기록 없음(90일 보존)"을 표시한다. | US-4 |
| R-15 | WHEN 운영자가 단계·기간(최대 90일)·선택 버전 키·값으로 추이를 조회하면, THE frontend SHALL 날짜별 p50·p95를 선 그래프와 표로 표시하고, 기간이 90일을 넘으면 요청하지 않고 이유를 표시한다. | US-4 |
| R-16 | WHEN 운영자가 매니페스트 경로·평가 비율(0~1)·분할 시드로 가져오기를 시작하면, THE frontend SHALL 가져오기를 요청하고, 409이면 "같은 매니페스트를 가져오는 중"을 표시한다. | US-5 |
| R-17 | WHILE 목록에 `PENDING`·`VALIDATING`·`REGISTERING` 가져오기나 `PENDING`·`RUNNING` 내보내기가 있으면, THE frontend SHALL 5초마다 그 항목의 상태를 다시 불러온다. | US-5 |
| R-18 | THE frontend SHALL 가져오기 상세에 상태, 영상·등록·실패·라벨·분할별 개수, 만든 Golden Set 버전(누르면 그 Golden Set 상세), 오류 목록을 표시한다. | US-5 |
| R-19 | WHEN 운영자가 Golden Set이나 기간(최대 90일)으로 특징 내보내기를 시작하면, THE frontend SHALL 둘 중 하나만 받도록 입력을 막고 요청하며, 완료되면 파일 경로·줄 수·영상 수를 표시한다. | US-5 |
| R-20 | IF 품질 API가 403을 돌려주면, THEN THE frontend SHALL 권한 없음 안내를 표시하고, 5xx·네트워크 오류면 다시 시도 버튼을 표시한다. | US-1 |
| R-21 | THE frontend SHALL 검토 큐 목록에 사유 필터(`reviewRequired`·`budget_exceeded`·`call_cap_reached`·`model_unavailable`·`alert_dismissed`·표본)를 두고, 예산·상한 사유 항목에는 "재분석 뒤 자동 판정됨" 안내를 표시한다. | US-1 |
| R-22 | THE frontend SHALL 처리 단계 화면에 긴급 알림 지연(p50·p95)과 `dismissed` 비율 리포트를 표시한다. | US-4 |

### 비기능 요구사항

| ID | 요구사항 |
| --- | --- |
| NFR-1 | THE frontend SHALL 검토 상세에서 "저장 후 다음"부터 다음 항목 표시까지 로컬 기준 응답 뒤 300ms 안에 그린다. |
| NFR-2 | THE frontend SHALL 품질 화면 코드를 별도 묶음(route lazy)으로 나눠 USER의 첫 화면 크기를 늘리지 않는다. |

## 5. 영향 범위

| 레포 / 서비스 | 변경 개요 | 담당 요구사항 |
| --- | --- | --- |
| frontend / features/quality (새 기능 폴더) | 품질 메뉴, 검토 큐, Golden Set, 평가 실행, 처리 단계, 데이터셋 화면 | R-1~R-20, NFR-1, NFR-2 |
| frontend / app/layout | OPERATOR 메뉴 표시 | R-1 |
| frontend / api/generated | quality-service 계약 생성 코드 | R-2~R-19 |
| backend / quality-service | 검토 항목 응답에 근거 프레임 서명 주소 | R-4 |
| docs | spec | — |

## 6. 계약 변경

| 계약 파일 | 변경 | 하위호환 |
| --- | --- | --- |
| `service-contracts/openapi/quality-service.yaml` | `ReviewItem.evidenceFrameUrls`(근거 프레임 서명 주소, 응답 필드) 추가, 1.1.0 → 1.2.0 | 예(응답 필드 추가) |
| `service-contracts/openapi/quality-service.yaml` | v5.1: 검토 사유 열거값·필터, 알림 지표 리포트(SPEC-029) | 예(추가) |

계약 묶음 3.13.0 → 3.14.0. v5.1 변경은 3.15.0 → 4.0.0(quality-service 응답 enum을 열린 목록으로 바꾼 하위호환 파괴 1회, ADR-0016. 나머지는 선택 필드·값 추가)

## 7. 성공 지표

- 로컬 compose의 quality-service(또는 계약 mock)로 검토 큐 맡기 → 라벨 → 저장 후 다음, Golden Set 넣기 → 버전 확정, 평가 실행 Gate 표시, 단계 추이 그래프, 가져오기 진행 표시가 화면에서 이어진다.

## 8. 미결 사항

- 해당 없음
