---
id: SPEC-011
title: ai-gateway 벡터 생성
status: Implementing
owner: <이름>
repos: [ai, docs]
created: 2026-11-03
updated: 2026-11-04
related: [ADR-0008, ADR-0010, SPEC-009]
---

# SPEC-011 ai-gateway 벡터 생성

> 이 문서에는 **무엇을, 왜**만 쓴다. 클래스, 테이블, 라이브러리 같은 구현 방법은 각 레포의 plan.md에 쓴다.

## 1. 배경과 목적

문장으로 장면 찾기와 이미지로 장면 찾기는 질의를 벡터로 바꿔 저장된 구간·크롭·텍스트 벡터와 비교한다([아키텍처 개요](../../architecture/overview.md) "검색 경로"). 질의 벡터는 저장된 벡터와 **같은 모델**로 만들어야 비교할 수 있으므로, 모델 선택과 모델 ID 기록을 한 곳에 모은다. 외부 AI 호출이 모이는 ai-gateway가 그 자리다([SPEC-009](../SPEC-009-ai-gateway-analyze/spec.md), [ADR-0008](../../adr/0008-industrial-safety-v3.md)).

이 spec은 ai-gateway에 `/v1/embed`를 더한다. 벡터는 세 종류다.

| taskType | 입력 | 모델 (프로필 값) | 쓰는 곳 |
| --- | --- | --- | --- |
| `embed_visual_text` | 영어 검색 문장 | 이미지·질의 인코더의 텍스트 쪽(기본 MobileCLIP2-S0) | 구간·크롭 벡터와 비교하는 시각 검색 |
| `embed_image` | 검색용 이미지 | 같은 인코더의 이미지 쪽 | 이미지로 장면 찾기 |
| `embed_text` | 이벤트 설명문·트랙 속성·검색 문장(한국어 포함) | 텍스트 임베딩 Adapter(운영 `text-embedding-3-small`, 로컬 Ollama `bge-m3`) | 텍스트 인덱스 적재(embedding-worker)와 텍스트 검색 |

인코더는 ai-gateway 안에서 직접 돌리는 모델이라 VLM이 내려가도 시각 검색은 동작해야 한다("AI Gateway" 가용성). 인코더 가중치는 이미지에 넣지 않고 기동할 때 모델 저장소 경로에서 내려받는다("모델과 플랫폼 교체"). PRD의 에픽은 아직 정의되지 않았다.

## 2. 범위

### 포함

- `/v1/embed`: taskType과 문장 목록 또는 이미지 경로 목록을 받아 입력 순서대로 벡터를 돌려준다. 결과마다 쓴 모델 ID와 차원을 싣는다.
- taskType 3종: `embed_visual_text`, `embed_image`, `embed_text`
- 이미지·질의 인코더: 프로필의 모델 ID·차원·가중치 경로로 기동할 때 한 번 로드한다. 가중치는 모델 저장소에서 내려받고 무결성을 확인한다. frame-encoder가 같은 모델 ID로 같은 벡터를 만들 수 있게 한다.
- 텍스트 임베딩 Adapter: `openai`, `openai_compatible`(로컬 Ollama), `mock`. SPEC-009의 Adapter 선택·mock 금지 규칙을 따른다.
- 입력 상한: taskType별 입력 개수, 문장 길이(프로필 값)
- 이미지 경로 검사: taskType별 허용 패턴(프로필 값). 검색용 이미지는 질의 전용 폴더 경로만 받는다.
- 호출 로그: 임베딩 호출도 `ai.ai_call_log`에 남긴다. 벡터와 입력 문장 원문은 남기지 않는다.
- 로컬 compose: 인코더 가중치를 로컬 저장소(SeaweedFS)에 올리는 절차, Ollama `bge-m3` 프로필

### 제외

- `/v1/parse`(질의 해석): SPEC-012
- 결과 캐시(질의 벡터 재사용 포함), 예산, 토큰 버킷, 단계 상향: SPEC-013
- 구간 프레임 4장 평균 벡터·크롭 벡터 생성과 벡터 파일 저장: frame-encoder spec. 이 spec은 같은 인코더를 쓸 수 있게 하는 데까지다.
- 검색용 이미지의 업로드·보관·삭제: search-service
- 벡터 저장과 검색(인덱스, RRF): search-service
- 모델 가중치를 OCI 이미지 볼륨 등 다른 방식으로 전달하는 것: 필요해지면 별도로 결정한다.

## 3. 사용자 시나리오

이 기능의 사용자는 ai-gateway를 부르는 내부 서비스(search-service, embedding-worker 등, 이하 호출자)와 운영자다.

### US-1 검색 문장을 시각 벡터로 바꿈 (P1)

search-service로서 영어 검색 문장을 구간 벡터와 같은 공간의 벡터로 받고 싶다. 왜냐하면 "지게차가 지나가는 장면" 같은 질의를 구간 벡터와 비교해야 하기 때문이다.

#### 인수 조건

- Given 허용된 호출자, When `embed_visual_text`로 문장 1개를 요청하면, Then 프로필 차원의 단위 벡터 1개와 인코더 모델 ID를 받는다.
- Given 같은 문장, When 다시 요청하면, Then 같은 벡터를 받는다.

### US-2 검색용 이미지를 벡터로 바꿈 (P1)

search-service로서 사용자가 올린 이미지를 구간·크롭 벡터와 같은 공간의 벡터로 받고 싶다. 왜냐하면 "이 사진과 비슷한 장면"을 찾아야 하기 때문이다.

#### 인수 조건

- Given 질의 전용 폴더의 이미지 경로, When `embed_image`를 요청하면, Then 인코더 차원의 단위 벡터와 모델 ID를 받는다.
- Given 허용 패턴 밖의 경로, When 요청하면, Then 인코더를 부르지 않고 거부된다.

### US-3 텍스트를 텍스트 벡터로 바꿈 (P1)

embedding-worker와 search-service로서 이벤트 설명문이나 검색 문장(한국어 포함)을 텍스트 벡터로 받고 싶다. 왜냐하면 텍스트 인덱스에 적재하고 같은 모델로 검색해야 하기 때문이다.

#### 인수 조건

- Given 문장 여러 개, When `embed_text`를 요청하면, Then 입력 순서대로 같은 개수의 벡터와 텍스트 임베딩 모델 ID를 받는다.
- Given 공급자가 응답하지 않으면, When 요청하면, Then "일시적으로 사용할 수 없음"을 받아 다시 시도할지 정할 수 있다.

### US-4 모델을 코드 변경 없이 바꾸고 결과마다 추적함 (P2)

운영자로서 인코더나 텍스트 임베딩 모델을 프로필만 바꿔 교체하고, 벡터마다 어떤 모델로 만들었는지 알고 싶다. 왜냐하면 다른 모델의 벡터끼리 섞어 검색하면 결과가 틀리기 때문이다.

#### 인수 조건

- Given 프로필의 인코더 모델 ID·가중치 경로를 바꾸면, When 재기동 후 요청하면, Then 새 모델 ID가 응답과 호출 로그에 남는다.
- Given 가중치가 손상됐거나 출력 차원이 프로필과 다르면, When 기동하면, Then 기동에 실패한다.

### US-5 VLM 장애와 상관없이 시각 검색이 동작함 (P2)

운영자로서 VLM 공급자나 텍스트 임베딩 공급자가 내려가도 시각 질의 벡터는 계속 만들어지기를 원한다. 왜냐하면 기본 검색은 유지돼야 하기 때문이다.

#### 인수 조건

- Given VLM·텍스트 임베딩 공급자에 연결할 수 없으면, When `embed_visual_text`를 요청하면, Then 벡터를 받는다.

### US-6 호출자별 사용량을 봄 (P3)

운영자로서 임베딩 호출의 호출자별 횟수·입력 수·지연·실패를 알고 싶다. 왜냐하면 비용과 장애를 호출자·모델 단위로 봐야 하기 때문이다.

#### 인수 조건

- Given 임베딩 호출, When 끝나면(성공·실패 모두), Then 호출 로그에 호출자·taskType·모델 ID·입력 수·지연·상태가 남고 벡터와 문장 원문은 남지 않는다.

## 4. 요구사항

### 기능 요구사항 (EARS)

| ID | 요구사항 | 시나리오 |
| --- | --- | --- |
| R-1 | WHEN 허용된 호출자가 `embed_visual_text`로 문장 목록을 요청하면, THE ai-gateway SHALL 이미지·질의 인코더의 텍스트 쪽으로 문장마다 벡터를 만들어 입력 순서대로 반환하고, 호출 ID·인코더 모델 ID·차원을 함께 반환한다. | US-1 |
| R-2 | WHEN 허용된 호출자가 `embed_image`로 이미지 경로 목록을 요청하면, THE ai-gateway SHALL 저장소에서 이미지를 읽어 인코더의 이미지 쪽으로 이미지마다 벡터를 만들어 입력 순서대로 반환하고, 호출 ID·인코더 모델 ID·차원을 함께 반환한다. | US-2 |
| R-3 | WHEN 허용된 호출자가 `embed_text`로 문장 목록을 요청하면, THE ai-gateway SHALL 프로필의 텍스트 임베딩 Adapter·모델로 문장마다 벡터를 만들어 입력 순서대로 반환하고, 호출 ID·모델 ID·차원을 함께 반환한다. | US-3 |
| R-4 | THE ai-gateway SHALL 반환하는 모든 벡터를 길이(L2 노름) 1로 정규화한다. | US-1, US-2, US-3 |
| R-5 | THE ai-gateway SHALL 같은 모델로 같은 입력을 다시 받으면 코사인 유사도 0.9999 이상인 벡터를 반환한다. | US-1 |
| R-6 | THE ai-gateway SHALL `embed_visual_text`·`embed_image` 응답의 모델 ID로, 같은 인코더를 쓰는 frame-encoder가 기록하는 `embedding_model`과 같은 문자열(프로필 값)을 반환한다. | US-4 |
| R-7 | IF 요청 형식이 맞지 않으면(taskType에 맞지 않는 입력 종류, 빈 목록, 빈 문장), THEN THE ai-gateway SHALL 모델을 부르지 않고 요청 오류로 거절한다. | US-1, US-3 |
| R-8 | IF 입력 개수가 그 taskType의 상한(프로필 값)을 넘으면, THEN THE ai-gateway SHALL 모델을 부르지 않고 입력 개수 초과 오류로 거절한다. | US-1, US-2, US-3 |
| R-9 | IF 모르는 taskType이면, THEN THE ai-gateway SHALL 요청 오류로 거절한다. | US-1 |
| R-10 | IF `embed_image`의 이미지 경로가 그 taskType의 허용 패턴(프로필 값)에 맞지 않으면, THEN THE ai-gateway SHALL 인코더를 부르지 않고 경로 거부 오류로 거절한다. | US-2 |
| R-11 | IF 이미지 경로의 객체가 저장소에 없으면, THEN THE ai-gateway SHALL 인코더를 부르지 않고 요청 오류로 거절한다. | US-2 |
| R-12 | IF 이미지를 디코딩할 수 없으면, THEN THE ai-gateway SHALL 이미지 해석 불가 오류로 거절한다. | US-2 |
| R-13 | IF 호출자 이름 헤더가 없거나 허용 호출자 목록에 없으면, THEN THE ai-gateway SHALL 모델을 부르지 않고 호출자 거부 오류로 거절한다(SPEC-009 R-16과 같은 목록). | US-6 |
| R-14 | IF 프로필에 그 taskType의 모델이 없으면, THEN THE ai-gateway SHALL 모델을 부르지 않고 모델 미설정 오류를 반환하며, 호출 로그에는 상태 `unavailable`을 남긴다. | US-4 |
| R-15 | WHEN 기동하면, THE ai-gateway SHALL 프로필의 인코더 모델 ID·차원·manifest 경로·manifest 해시를 검증하고, 모델 저장소에서 manifest와 manifest에 적힌 가중치 파일을 내려받아 각 해시를 확인한 뒤 인코더를 한 번 로드한다(ADR-0010 ②). | US-4 |
| R-16 | IF manifest나 가중치를 내려받을 수 없거나, manifest 해시가 프로필과 다르거나, 가중치 해시가 manifest와 다르거나, manifest의 모델 종류·모델 ID·차원이 프로필과 맞지 않거나, 로드에 실패하면, THEN THE ai-gateway SHALL 기동에 실패한다. | US-4 |
| R-17 | IF 로드한 인코더의 텍스트 쪽이나 이미지 쪽 출력 차원이 프로필 차원과 다르면, THEN THE ai-gateway SHALL 기동에 실패한다. | US-4 |
| R-18 | WHERE 로컬 캐시에 해시가 같은 manifest와 manifest의 해시와 맞는 가중치가 이미 있으면, THE ai-gateway SHALL 다시 내려받지 않고 그 파일을 쓴다. | US-4 |
| R-19 | IF 텍스트 임베딩 공급자가 돌려준 벡터의 차원이 프로필 차원과 다르거나 벡터 개수가 입력 개수와 다르면, THEN THE ai-gateway SHALL 벡터를 반환하지 않고 상태 `invalid_output`으로 기록한 뒤 공급자 오류를 반환한다. | US-3, US-4 |
| R-20 | IF 텍스트 임베딩 공급자가 제한 시간(프로필 값) 안에 응답하지 않거나 연결할 수 없거나 일시 오류(429, 5xx)를 돌려주면, THEN THE ai-gateway SHALL 상태 `unavailable`로 기록하고 "일시적으로 사용할 수 없음" 오류를 반환한다. | US-3 |
| R-21 | IF 텍스트 임베딩 공급자가 요청 자체를 거부하면(429 외 4xx), THEN THE ai-gateway SHALL 상태 `failed`로 기록하고 공급자 오류를 반환한다. | US-3 |
| R-22 | THE ai-gateway SHALL `embed_visual_text`·`embed_image` 처리를 VLM Adapter·텍스트 임베딩 Adapter의 연결 상태와 상관없이 수행한다. | US-5 |
| R-23 | WHEN 임베딩 요청 처리가 끝나면(성공·실패 모두), THE ai-gateway SHALL 호출 ID, 호출자, taskType, 모델 ID, 입력 개수, 지연, 상태, 공급자가 알려 준 입력 토큰 수, 보낸 이미지 경로를 호출 로그에 저장하고, 벡터와 입력 문장 원문은 저장하지 않는다. | US-6 |
| R-24 | IF 인코더를 쓰는 프로필인데 mock 인코더를 고르고 mock 허용 설정이 켜져 있지 않으면, THEN THE ai-gateway SHALL 기동에 실패한다(SPEC-009 R-15와 같은 규칙). | US-4 |
| R-25 | THE ai-gateway SHALL `/ready`를 인코더 로드(R-15)까지 끝난 뒤에만 200으로 반환한다(SPEC-009 R-23에 조건 추가). | US-4 |
| R-26 | IF 문장 길이가 그 taskType의 상한(프로필 값)을 넘으면, THEN THE ai-gateway SHALL 모델을 부르지 않고 요청 오류로 거절한다. | US-1, US-3 |

### 비기능 요구사항

| ID | 요구사항 |
| --- | --- |
| NFR-1 | THE ai-gateway SHALL `embed_visual_text` 문장 1개 요청을 p95 150ms 이하로 처리한다(로컬 compose, CPU, 기본 인코더). |
| NFR-2 | THE ai-gateway SHALL `embed_image` 이미지 1장 요청을 저장소 읽기를 포함해 p95 300ms 이하로 처리한다(로컬 compose, CPU, 기본 인코더, 1280px 이하 JPEG). |
| NFR-3 | THE ai-gateway SHALL 인코더 계산 중에도 `/health`에 1초 안에 응답한다(인코더 계산이 요청 처리 루프를 막지 않는다). |
| NFR-4 | THE ai-gateway SHALL 인코더 라이브러리와 공급자 SDK를 인코더·Adapter 구현 안에서만 부른다. 인코더 구현은 frame-encoder가 같은 코드를 쓸 수 있게 서비스 밖 공용 위치에 둔다. |
| NFR-5 | THE ai-gateway SHALL 애플리케이션 로그에 입력 문장 원문, 이미지 내용, 벡터, 공급자 API 키를 남기지 않는다. |
| NFR-6 | THE ai-gateway SHALL 인코더 가중치를 서비스 이미지에 넣지 않는다. |

## 5. 영향 범위

| 레포 / 서비스 | 변경 개요 | 담당 요구사항 |
| --- | --- | --- |
| ai / ai-gateway | `/v1/embed`, 텍스트 임베딩 Adapter, 입력 상한·경로 검사, 호출 로그 확장, 인코더 로드와 `/ready` 조건, 프로필(로컬·mock) | R-1~R-26, NFR-1~NFR-3, NFR-5, NFR-6 |
| ai / libs | 이미지·질의 인코더 공용 인터페이스와 구현, manifest·가중치 내려받기·해시 확인 | R-4~R-6, R-15~R-18, R-24, NFR-4 |
| docs | ai-gateway API 계약에 `/v1/embed` 추가, 로컬 compose에 가중치 올리기 절차와 Ollama `bge-m3` 안내 | — |
| gitops·infra | (이후) 모델 저장소 경로 읽기 권한, 가중치 캐시용 디스크. 사용자 지시 시 진행한다. | — |

## 6. 계약 변경

| 계약 파일 | 변경 | 하위호환 |
| --- | --- | --- |
| `service-contracts/openapi/ai-gateway.yaml` | `POST /v1/embed` 추가(요청: taskType, 문장 목록 또는 이미지 경로 목록 / 응답: 호출 ID, 모델 ID, 차원, 벡터 목록). 오류 코드 추가: 입력 개수 초과, 이미지 해석 불가, 모델 미설정. 버전 0.1.0 → 0.2.0 | 예(경로·코드 추가) |
| `service-contracts/models/manifest.schema.json` | 모델 산출물 manifest 형식 추가(ADR-0010 ②, v4 전환 D-5). 인코더 가중치는 이 manifest로 받는다(R-15~R-18). 계약 묶음 2.1.0 | 예(파일 추가) |
| `docs/architecture/overview.md` | 변경 없음. "AI Gateway"·"모델과 플랫폼 교체"에 적힌 내용을 따른다. | 해당 없음 |

## 7. 성공 지표

- 로컬 compose에서 기본 인코더로 `embed_visual_text`·`embed_image`가 동작하고, "a forklift" 문장 벡터가 지게차가 있는 이미지 벡터와 지게차가 없는 이미지 벡터 중 앞쪽과 더 가깝다.
- 로컬 Ollama `bge-m3`로 `embed_text`가 코드 변경 없이 프로필만 바꿔 동작한다.
- Ollama를 멈춘 상태에서도 `embed_visual_text`가 동작한다.

## 8. 미결 사항

- 해당 없음
