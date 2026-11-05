---
id: SPEC-012
title: ai-gateway 질의 해석
status: Approved
owner: <이름>
repos: [ai, docs]
created: 2026-11-04
updated: 2026-11-06
related: [ADR-0008, ADR-0010, ADR-0012, SPEC-009, SPEC-011]
---

# SPEC-012 ai-gateway 질의 해석

> 이 문서에는 **무엇을, 왜**만 쓴다. 클래스, 테이블, 라이브러리 같은 구현 방법은 각 레포의 plan.md에 쓴다.

## 1. 배경과 목적

문장으로 장면 찾기는 사용자의 한국어 검색 문장을 그대로 인코더에 넣지 않는다. 기본 인코더(MobileCLIP2-S0)의 텍스트 쪽은 영어 위주라 한국어 문장을 넣으면 결과가 나쁘다. 그래서 검색 문장을 먼저 **표준 질의**로 해석하고, 거기서 만든 영어 검색 문장으로 시각 검색을 한다([아키텍처 개요](../../architecture/overview.md) "검색 경로" 1단계, [ADR-0008](../../adr/0008-industrial-safety-v3.md) "질의 해석은 규칙 사전이 먼저").

표준 질의는 다음 용도에 쓴다.

| 용도 | 쓰는 값 |
| --- | --- |
| 검색 경로 선택: 장면 찾기(`video_retrieval`) 또는 시간·상태 질문 답변(`temporal_video_rag`) | route |
| 시각 검색(`embed_visual_text`, [SPEC-011](../SPEC-011-ai-gateway-embed/spec.md)) | 영어 검색 문장 |
| bbox 주석(grounding) 대상 | 대상어 1~3개 |
| 텍스트 인덱스 필터 | 이벤트 유형(분류 체계 enum) |
| 검색 결과 재사용 | 표준 질의 문자열 |

해석은 **규칙 사전**이 먼저다. 규칙 사전은 결정적이라 같은 문장에 항상 같은 결과를 내고, 수 ms 안에 끝나며 비용이 없다. 사전에 없는 한국어 문장만 LLM(`query_parse`)으로 보조하고, 그래도 안 되면 산업 CCTV 기본 대상인 `person`으로 제한한다. 결과에는 어떤 방법으로 해석했는지(`industrial-rule`·`english-phrase`·`llm`·`safe-fallback`) 표시한다.

규칙 사전과 LLM 프롬프트는 ai-gateway 안에만 있다("AI Gateway" 인터페이스). 둘 다 Prompt Registry의 일부라 원본은 ai 레포 `services/ai-gateway/registry/`이고, 레포 경계를 넘는 분류 체계만 `service-contracts/taxonomy/`를 따른다([ADR-0012](../../adr/0012-prompt-registry-source.md)). 표준 질의 문자열도 ai-gateway가 만든다. 정규화 규칙과 사전·프롬프트 버전을 아는 곳이 ai-gateway뿐이고, search-service와 grounding 등 여러 곳이 같은 값을 써야 하기 때문이다. 단계별 재사용 키(sourceId, 분석 버전, 인코더 모델 등을 붙인 키)는 search-service가 이 문자열에 자기 값을 붙여 만든다. PRD의 에픽은 아직 정의되지 않았다.

## 2. 범위

### 포함

- `/v1/parse`: 검색 문장 하나를 받아 표준 질의를 돌려준다. 표준 질의는 route, 대상어 1~3개, 이벤트 유형 목록, 영어 검색 문장, 해석 방법, 해석 근거, 사전 버전, 프롬프트 버전, 분류 체계 버전, 표준 질의 문자열로 이루어진다.
- 질의 사전 v1: 시간·상태 표현 목록, 한국어 표현 → 영어 대상어·이벤트 유형 대응표, 불용 표현, 영어 검색 문장 형식. Prompt Registry(ai 레포)에 버전 파일로 두고, Registry 묶음(SPEC-009 R-26)에 함께 들어간다. 첫 내용은 기존 vlm_project의 규칙(`KOREAN_RULES`)에서 시작하고 분류 체계 v2 이벤트 유형 8종의 표현을 더한다.
- 영어 문장 처리: 사전에 맞는 한국어 표현이 없고 문장이 영어 위주면 불용어를 지운 구문을 대상어로 쓴다.
- LLM 보조 `query_parse`: Prompt Registry의 프롬프트와 출력 스키마, 프로필의 Adapter·모델(SPEC-009의 Adapter 선택·mock 금지 규칙). 이미지는 보내지 않는다.
- 안전 대체(`safe-fallback`): LLM이 미설정이거나 실패하면 오류 대신 `person`으로 제한한 표준 질의를 돌려준다.
- 입력 검사: 빈 문장, 길이 상한(프로필 값), 호출자 허용 목록(SPEC-009 R-16과 같은 목록)
- 호출 로그: 해석 호출도 `ai.ai_call_log`에 남긴다. 검색 문장 원문과 모델 원문은 남기지 않는다.
- 로컬: 로컬 Ollama 모델로 `query_parse`를 쓰는 프로필

### 제외

- 표준 질의의 속성 조건(보호구 착용 여부, 역할, 장비 등): 분류 체계에 속성 enum이 생기는 spec에서 더한다.
- 시간 조건 해석("오후 3시 이후" 같은 절대·상대 시각을 필터로 바꾸는 것): 시간 필터의 의미는 search-service가 정한 뒤 더한다. 이번 spec에서는 시간·상태 표현을 route를 나누는 데만 쓴다.
- 사전에 일부만 맞는 문장의 사전 밖 단어를 LLM으로 보충하는 것: 사전에 하나라도 맞으면 LLM을 부르지 않는다. 빠진 단어는 질의 로그로 모아 사전을 보강한다.
- 질의 해석 결과 캐시(Redis → DB), 예산, 토큰 버킷: SPEC-016
- 질의 로그(질의 원문, 이동·재생 구간, 맞음·틀림)와 `safe-fallback` 질의 모으기: search-service
- 단계별 재사용 키 생성과 검색 결과 재사용: search-service
- route에 따른 Video RAG 처리: search-service와 이후 `video_rag` spec

## 3. 사용자 시나리오

이 기능의 사용자는 ai-gateway를 부르는 search-service(이하 호출자)와 운영자다.

### US-1 한국어 검색 문장을 표준 질의로 바꿈 (P1)

search-service로서 "안전모 안 쓴 작업자 찾아줘" 같은 한국어 문장을 영어 검색 문장과 대상어로 받고 싶다. 왜냐하면 인코더 텍스트 쪽이 영어 위주라 한국어 원문으로는 시각 검색이 잘 되지 않기 때문이다.

#### 인수 조건

- Given 사전에 있는 표현이 든 문장, When 해석을 요청하면, Then 사전의 영어 대상어 1~3개, 그 대상어로 만든 영어 검색 문장, 해석 방법 `industrial-rule`을 받는다.
- Given "쓰러진 사람" 같은 이벤트 표현, When 해석을 요청하면, Then 이벤트 유형 `fall`을 받는다.
- Given 같은 문장, When 다시 요청하면, Then 같은 표준 질의를 받는다.

### US-2 시간·상태 질문을 나눔 (P1)

search-service로서 "작업 종료 후 남은 위험 요소" 같은 질문을 장면 찾기와 구분하고 싶다. 왜냐하면 시간·상태 질문은 장면 하나를 찾는 것이 아니라 근거를 모아 답해야 하기 때문이다.

#### 인수 조건

- Given 시간·상태 표현이 든 문장, When 해석을 요청하면, Then route `temporal_video_rag`를 받는다.
- Given 시간·상태 표현이 없는 문장, When 해석을 요청하면, Then route `video_retrieval`을 받는다.

### US-3 영어 검색 문장을 그대로 씀 (P2)

search-service로서 "forklift near a worker" 같은 영어 문장을 받으면 그대로 대상어로 쓰고 싶다. 왜냐하면 영어 문장은 인코더에 바로 넣을 수 있기 때문이다.

#### 인수 조건

- Given 사전에 맞는 한국어 표현이 없는 영어 문장, When 해석을 요청하면, Then "find", "show" 같은 불용어를 지운 구문을 대상어로, 해석 방법 `english-phrase`를 받는다.

### US-4 사전 밖 질의를 LLM으로 보조함 (P2)

search-service로서 사전에 없는 한국어 문장도 시각 대상어로 받고 싶다. 왜냐하면 사전이 모든 표현을 담을 수 없기 때문이다.

#### 인수 조건

- Given 사전에 맞는 표현이 없는 한국어 문장과 `query_parse` 모델이 설정된 프로필, When 해석을 요청하면, Then LLM이 고른 영어 대상어 1~3개와 해석 방법 `llm`, 프롬프트 버전을 받는다.

### US-5 LLM이 없어도 검색이 이어짐 (P2)

운영자로서 LLM 공급자가 내려가거나 설정되지 않아도 검색이 멈추지 않기를 원한다. 왜냐하면 기본 검색은 VLM 장애와 상관없이 유지돼야 하기 때문이다("AI Gateway" 가용성).

#### 인수 조건

- Given LLM 공급자에 연결할 수 없거나 출력이 스키마에 맞지 않으면, When 사전 밖 한국어 문장을 해석하면, Then 오류가 아니라 대상어 `person`, 해석 방법 `safe-fallback`인 표준 질의를 받는다.
- Given LLM 공급자에 연결할 수 없으면, When 사전에 있는 문장을 해석하면, Then `industrial-rule` 결과를 받는다.

### US-6 결과 재사용에 같은 키를 씀 (P2)

search-service로서 표현만 다른 같은 질의("지게차 찾아줘", "지게차 장면")에 같은 키를 받고 싶다. 왜냐하면 저장된 검색 결과를 다시 쓰고, 사전이나 프롬프트가 바뀌면 예전 결과와 섞이지 않아야 하기 때문이다.

#### 인수 조건

- Given 해석 결과가 같은 두 문장, When 각각 해석하면, Then 같은 표준 질의 문자열을 받는다.
- Given 사전 버전이 바뀌면, When 같은 문장을 해석하면, Then 다른 표준 질의 문자열을 받는다.

### US-7 사전을 코드 변경 없이 보강하고 사용을 추적함 (P3)

운영자로서 사전을 버전 파일만 바꿔 보강하고, 해석 방법별 호출 수와 LLM 호출 지연을 알고 싶다. 왜냐하면 `safe-fallback` 비율을 보고 사전을 늘려야 하기 때문이다.

#### 인수 조건

- Given 형식이 틀린 사전 파일, When 기동하면, Then 기동에 실패한다.
- Given 해석 호출, When 끝나면, Then 호출 로그에 호출자·해석 방법·사전 버전·지연·상태가 남고 검색 문장 원문은 남지 않는다.

## 4. 요구사항

### 기능 요구사항 (EARS)

| ID | 요구사항 | 시나리오 |
| --- | --- | --- |
| R-1 | WHEN 허용된 호출자가 `/v1/parse`로 검색 문장을 요청하면, THE ai-gateway SHALL 호출 ID와 표준 질의(route, 대상어, 이벤트 유형, 영어 검색 문장, 해석 방법, 해석 근거, 사전 버전, 프롬프트 버전, 표준 질의 문자열)를 반환한다. | US-1 |
| R-2 | THE ai-gateway SHALL 규칙을 적용하기 전에 검색 문장을 정규화한다(앞뒤 공백 제거, 연속 공백을 하나로, 영문 소문자화, 사전의 불용 표현 제거). | US-1, US-6 |
| R-3 | WHEN 정규화한 문장에 사전의 시간·상태 표현이 하나 이상 있으면, THE ai-gateway SHALL route를 `temporal_video_rag`로 둔다. | US-2 |
| R-4 | WHEN 정규화한 문장에 사전의 시간·상태 표현이 없으면, THE ai-gateway SHALL route를 `video_retrieval`로 둔다. | US-2 |
| R-5 | WHEN 정규화한 문장에 사전의 한국어 표현이 하나 이상 있으면, THE ai-gateway SHALL 맞은 표현의 영어 대상어를 사전에 적힌 순서로 중복 없이 최대 3개 대상어로 두고, 해석 방법을 `industrial-rule`로 둔다. | US-1 |
| R-6 | IF 맞은 사전 표현끼리 문장에서 겹치면(예: "안전모 미착용"과 "안전모"), THEN THE ai-gateway SHALL 더 긴 표현만 적용한다. | US-1 |
| R-7 | WHEN 맞은 사전 표현에 이벤트 유형이 지정돼 있으면, THE ai-gateway SHALL 그 이벤트 유형(분류 체계 v2 enum, `other` 제외)을 사전에 적힌 순서로 중복 없이 이벤트 유형 목록에 넣는다. 맞은 표현에 이벤트 유형이 없으면 목록은 비어 있다. | US-1 |
| R-8 | WHEN 사전의 한국어 표현이 맞지 않고 문장이 영어 위주이면(영문자가 공백을 뺀 글자의 절반 이상이고 3자 이상), THE ai-gateway SHALL 사전의 영어 불용어와 영문·숫자·공백·하이픈 밖의 문자를 지운 구문을 대상어 하나로 두고, 해석 방법을 `english-phrase`로 둔다. | US-3 |
| R-9 | IF R-8에서 불용어를 지운 구문이 비면, THEN THE ai-gateway SHALL 대상어를 `person`으로, 해석 방법을 `safe-fallback`으로 둔다. | US-3 |
| R-10 | WHEN 사전의 한국어 표현이 맞지 않고 문장이 영어 위주가 아니면, THE ai-gateway SHALL 프로필의 `query_parse` Adapter·모델에 Prompt Registry의 프롬프트로 문장을 보내고(이미지 없음, temperature 0), 출력에서 JSON 객체를 꺼내 출력 스키마(영어 대상어 1~3개, 분류 체계 이벤트 유형)로 검증한다. | US-4 |
| R-11 | WHEN R-10의 출력이 스키마 검증을 통과하면, THE ai-gateway SHALL 출력의 대상어·이벤트 유형을 쓰고, 해석 방법을 `llm`, 프롬프트 버전을 그 프롬프트의 버전 ID로 둔다. | US-4 |
| R-12 | IF 프로필에 `query_parse` 모델이 없으면, THEN THE ai-gateway SHALL 모델을 부르지 않고 대상어 `person`, 빈 이벤트 유형 목록, 해석 방법 `safe-fallback`인 표준 질의를 200으로 반환하며, 호출 로그에는 상태 `unavailable`을 남긴다. | US-5 |
| R-13 | IF `query_parse` 공급자가 제한 시간(프로필 값) 안에 응답하지 않거나 연결할 수 없거나 오류를 돌려주면, THEN THE ai-gateway SHALL R-12와 같은 `safe-fallback` 표준 질의를 200으로 반환하고, 호출 로그에는 일시 오류(429, 5xx, 시간 초과, 연결 불가)면 `unavailable`, 그 밖의 거부면 `failed`를 남긴다. | US-5 |
| R-14 | IF `query_parse` 출력에서 JSON을 찾지 못하거나 출력 스키마 검증에 실패하면, THEN THE ai-gateway SHALL R-12와 같은 `safe-fallback` 표준 질의를 200으로 반환하고, 호출 로그에 상태 `invalid_output`을 남긴다. | US-5 |
| R-15 | THE ai-gateway SHALL route 결정(R-3, R-4)을 해석 방법과 상관없이 사전으로만 한다. | US-2, US-4 |
| R-16 | THE ai-gateway SHALL 영어 검색 문장을 대상어로부터 사전의 영어 검색 문장 형식으로 만든다. 같은 대상어 목록이면 같은 문장이다. | US-1 |
| R-17 | THE ai-gateway SHALL 해석 근거를 해석 방법과 맞은 사전 표현으로 만든다. LLM 출력의 설명문은 해석 근거에 넣지 않는다. | US-1, US-4 |
| R-18 | THE ai-gateway SHALL 표준 질의 문자열을 route, 대상어, 이벤트 유형, 해석 방법, 사전 버전, 분류 체계 버전으로 만들고, 해석 방법이 `llm`일 때만 프롬프트 버전을 더한다. 같은 값이면 항상 같은 문자열이고, 하나라도 다르면 다른 문자열이다. | US-6 |
| R-19 | THE ai-gateway SHALL 해석 방법이 `llm`이 아니면 응답의 프롬프트 버전을 비워 둔다. | US-6 |
| R-20 | IF 검색 문장이 비었거나 정규화 뒤 비면, THEN THE ai-gateway SHALL 모델을 부르지 않고 요청 오류로 거절한다. | US-1 |
| R-21 | IF 검색 문장 길이가 상한(프로필 값)을 넘으면, THEN THE ai-gateway SHALL 모델을 부르지 않고 요청 오류로 거절한다. | US-1 |
| R-22 | IF 호출자 이름 헤더가 없거나 허용 호출자 목록에 없으면, THEN THE ai-gateway SHALL 모델을 부르지 않고 호출자 거부 오류로 거절한다(SPEC-009 R-16과 같은 목록). | US-7 |
| R-23 | WHEN 기동하면, THE ai-gateway SHALL Prompt Registry(설정돼 있으면 Registry 묶음)의 질의 사전 파일을 읽어 검증한다(형식, 대상어는 영어 구문, 이벤트 유형은 분류 체계 enum, 표현 중복 없음, 버전 이름 있음). | US-7 |
| R-24 | IF 질의 사전 파일이 없거나 검증에 실패하면, THEN THE ai-gateway SHALL 기동에 실패한다. | US-7 |
| R-25 | THE ai-gateway SHALL `/ready`를 질의 사전 검증(R-23)까지 끝난 뒤에만 200으로 반환한다(SPEC-009 R-23에 조건 추가). | US-7 |
| R-26 | THE ai-gateway SHALL 사전 해석(R-3~R-9)을 VLM Adapter·텍스트 임베딩 Adapter의 연결 상태와 상관없이 수행한다. | US-5 |
| R-27 | WHEN 해석 요청 처리가 끝나면(`safe-fallback` 포함, 요청 오류·호출자 거부로 거절한 경우 제외), THE ai-gateway SHALL 호출 ID, 호출자, taskType `query_parse`, 해석 방법, 사전 버전, LLM을 불렀으면 모델 ID·프롬프트 버전·입력 토큰 수, 지연, 상태를 호출 로그에 저장하고, 검색 문장 원문과 모델 원문은 저장하지 않는다. | US-7 |
| R-28 | IF `query_parse` 프로필이 `mock` Adapter를 쓰는데 mock 허용 설정이 켜져 있지 않으면, THEN THE ai-gateway SHALL 기동에 실패한다(SPEC-009 R-15와 같은 규칙). | US-4 |
| R-29 | THE ai-gateway SHALL 사전 버전을 사전 파일의 버전 이름과 사전 내용 해시로 만들어, 버전 이름을 그대로 두고 내용만 바꿔도 다른 사전 버전이 되게 한다. | US-6 |
| R-30 | THE ai-gateway SHALL 응답과 호출 로그에 질의 사전과 `query_parse` 출력 스키마가 참조하는 분류 체계 버전(예: `v2`)을 남긴다(SPEC-009 R-29와 같은 의미). 해석 방법과 상관없이 같은 값이다. | US-6 |
| R-31 | IF 질의 사전이 참조하는 분류 체계 버전과 `query_parse` 출력 스키마가 참조하는 분류 체계 버전이 다르면, THEN THE ai-gateway SHALL 기동에 실패한다. | US-7 |

### 비기능 요구사항

| ID | 요구사항 |
| --- | --- |
| NFR-1 | THE ai-gateway SHALL LLM을 부르지 않는 해석 요청(`industrial-rule`·`english-phrase`)을 호출 로그 저장을 포함해 p95 30ms 이하로 처리한다(로컬 compose). |
| NFR-2 | THE ai-gateway SHALL LLM을 부르는 해석 요청을 `query_parse` 제한 시간(프로필 값) + 100ms 안에 끝낸다. |
| NFR-3 | THE ai-gateway SHALL 애플리케이션 로그에 검색 문장 원문, 모델 원문, 공급자 API 키를 남기지 않는다. |
| NFR-4 | THE ai-gateway SHALL 질의 사전 v1로 사전 단위 예시 세트(사전 항목마다 1개 이상, 이벤트 유형 8종마다 1개 이상, 시간·상태 표현 5개 이상)를 기대한 route·대상어·이벤트 유형으로 모두 해석한다. |

## 5. 영향 범위

| 레포 / 서비스 | 변경 개요 | 담당 요구사항 |
| --- | --- | --- |
| ai / ai-gateway | `/v1/parse`, 정규화·사전 해석·영어 구문 처리, `query_parse` 호출과 안전 대체, 표준 질의 문자열, 사전 로드·검증과 `/ready` 조건, 호출 로그, 프로필(로컬·mock), Prompt Registry에 질의 사전 v1·스키마와 `query_parse` 프롬프트·입출력 스키마 | R-1~R-31, NFR-1~NFR-4 |
| docs | ai-gateway API 계약에 `/v1/parse` 추가 | R-1 |
| backend / search-service | (이후, 다른 담당자) `/v1/parse`를 불러 route·영어 검색 문장·표준 질의 문자열을 쓴다. 이 spec에서는 바꾸지 않는다. | — |

## 6. 계약 변경

| 계약 파일 | 변경 | 하위호환 |
| --- | --- | --- |
| `service-contracts/openapi/ai-gateway.yaml` | `POST /v1/parse` 추가(요청: 검색 문장 / 응답: 호출 ID, route, 대상어, 이벤트 유형, 영어 검색 문장, 해석 방법, 해석 근거, 사전 버전, 프롬프트 버전, 분류 체계 버전, 표준 질의 문자열). 표준 질의 문자열은 해석하지 않고 그대로 쓰는 값이라고 설명에 적는다. 버전 0.2.1 → 0.3.0, 계약 묶음 2.6.0 → 2.7.0 | 예(경로 추가) |
| 질의 사전 v1·스키마, `query_parse` 프롬프트·입출력 스키마 | 계약이 아니다. ai 레포 Prompt Registry에 둔다([ADR-0012](../../adr/0012-prompt-registry-source.md)). 분류 체계는 기존 v2를 참조만 한다. | 해당 없음 |
| `docs/architecture/overview.md` | 변경 없음. "검색 경로" 1단계와 "AI Gateway"에 적힌 내용을 따른다. 속성·시간 조건은 이후 spec에서 더한다. | 해당 없음 |

## 7. 성공 지표

- 사전 단위 예시 세트(NFR-4)가 모두 기대한 결과로 해석된다.
- 로컬 compose에서 "안전모 안 쓴 작업자" 해석 결과의 영어 검색 문장으로 `embed_visual_text`를 부를 수 있다.
- Ollama를 멈춘 상태에서도 사전에 있는 문장은 `industrial-rule`, 사전 밖 한국어 문장은 `safe-fallback`으로 200을 받는다.

## 8. 미결 사항

- 해당 없음
