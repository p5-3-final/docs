---
id: SPEC-018
title: 학습용 보존 동의와 보존 키
status: Implementing
owner: <이름>
repos: [backend, docs]
created: 2026-11-06
updated: 2026-11-06
related: [ADR-0010, ADR-0011, SPEC-003]
---

# SPEC-018 학습용 보존 동의와 보존 키

> 이 문서에는 **무엇을, 왜**만 쓴다. 클래스, 테이블, 라이브러리 같은 구현 방법은 각 레포의 plan.md에 쓴다.

## 1. 배경과 목적

지금은 영상을 지우면(`video.deleted`) 모든 서비스가 그 영상의 파생 데이터를 모두 지운다. 그래서 예측 모델을 학습할 데이터가 쌓이지 않는다. [ADR-0011](../../adr/0011-derived-data-retention.md)은 사용자가 동의한 영상에 한해, 사람을 알아볼 수 없는 파생 데이터(등급 (b))를 영상 삭제 뒤 1년 동안 보존하기로 했다.

이 spec은 그 결정 중 media-service가 맡는 부분을 정한다.

- 동의: 영상별로 고르고, 계정 기본값을 둔다. 기본값은 "보존하지 않음"이다.
- 보존 키: 영상을 지울 때 media-service만 가진 비밀 키로 sourceId의 HMAC-SHA256을 계산해 `video.deleted`에 싣는다. 다른 서비스는 받은 키를 그대로 쓴다. 비밀 키 없이는 보존 데이터를 원래 영상과 다시 이을 수 없다.
- 철회: 삭제한 영상의 동의를 철회하면 보존 키를 실은 철회 이벤트를 발행하고, 각 서비스가 그 키의 보존 데이터를 지운다.
- 최소 기록: 철회할 때 보존 키를 다시 계산하려고, 지운 영상의 sourceId·소유자·동의 여부·삭제 시각만 1년 동안 남긴다. 파일 이름은 남기지 않는다.

각 서비스가 자기 데이터 중 무엇을 (b)로 보존하고 어떻게 지우는지는 각 서비스 spec에서 정한다. 이 spec은 그들이 받을 이벤트를 정한다.

## 2. 범위

### 포함

- 계정 기본값 조회·변경
- 업로드 자리 발급 때 동의 고르기(없으면 계정 기본값), 영상이 남아 있는 동안 동의 바꾸기
- 영상 응답의 동의 여부
- 동의한 영상을 지울 때 보존 키·보존 만료 시각을 `video.deleted`에 싣고 최소 기록을 남기기
- 보존 중인 삭제 영상 목록, 영상별 철회, 전체 철회와 철회 이벤트(`video.retention.revoked`)
- 보존 만료 시각이 지난 최소 기록 지우기
- REST 계약(`media-service.yaml`)과 이벤트 계약(`video.deleted`, `video.retention.revoked`)

### 제외

- 각 서비스의 (b) 데이터 보존·만료·철회 처리: 각 서비스 spec. 다른 담당자 서비스는 이 계약을 보고 각자 구현한다.
- 학습 데이터 내보내기(ADR-0010 ⑨): quality spec
- 외부 데이터셋 영상(ADR-0010 ⑨): Golden Set 관리 규칙을 따르고 이 spec을 적용하지 않는다.
- 비밀 키 교체 절차
- 동의 화면(frontend): 별도 spec
- 운영 비밀 키 주입(Kubernetes Secret): 사용자 지시 시 gitops에서 한다.

## 3. 사용자 시나리오

### US-1 학습용 보존에 동의 (P1)

현장 관리자로서 내 영상에서 나온 비식별 기록을 예측 모델 학습에 쓰도록 허락하고 싶다. 왜냐하면 영상은 지우더라도 위험 예측이 나아지기를 원하기 때문이다.

#### 인수 조건

- Given 계정 기본값을 바꾼 적 없는 사용자, When 영상을 올리면, Then 그 영상은 보존에 동의하지 않은 상태다.
- Given 계정 기본값을 "보존함"으로 바꾼 사용자, When 동의 값 없이 영상을 올리면, Then 그 영상은 보존에 동의한 상태다.
- Given 보존에 동의한 영상, When 지우면, Then `video.deleted`에 보존 키와 보존 만료 시각이 실리고 보존 중인 삭제 영상 목록에 나온다.

### US-2 동의하지 않은 영상 삭제 (P1)

사용자로서 동의하지 않은 영상은 지금처럼 모두 지워지기를 원한다. 왜냐하면 동의하지 않은 데이터가 남으면 안 되기 때문이다.

#### 인수 조건

- Given 보존에 동의하지 않은 영상, When 지우면, Then `video.deleted`에 보존 정보가 없고 최소 기록도 남지 않는다.

### US-3 동의 철회 (P1)

사용자로서 이미 지운 영상의 보존 동의를 거두고 싶다. 왜냐하면 마음이 바뀌면 남은 기록도 지워져야 하기 때문이다.

#### 인수 조건

- Given 보존 중인 삭제 영상, When 그 영상의 동의를 철회하면, Then 보존 키를 실은 `video.retention.revoked`가 한 번 발행되고 목록에서 사라진다.
- Given 보존 중인 삭제 영상 3개, When 전체 철회를 요청하면, Then 철회 이벤트가 3개 발행되고 목록이 빈다.
- Given 아직 남아 있는 영상, When 동의를 끄면, Then 철회 이벤트는 발행되지 않고, 나중에 지울 때 보존 정보 없이 지워진다.

## 4. 요구사항

### 기능 요구사항 (EARS)

| ID | 요구사항 | 시나리오 |
| --- | --- | --- |
| R-1 | WHEN 사용자가 보존 설정을 요청하면, THE media-service SHALL 요청자 계정의 기본 동의 값을 반환하고, 바꾼 적이 없으면 `false`를 반환한다. | US-1 |
| R-2 | WHEN 사용자가 기본 동의 값을 바꾸면, THE media-service SHALL 새 값을 저장하고 이미 있는 영상의 동의는 바꾸지 않는다. | US-1 |
| R-3 | WHEN 업로드 자리 발급 요청에 동의 값이 없으면, THE media-service SHALL 그 시점의 계정 기본값을 영상의 동의로 저장한다. | US-1 |
| R-4 | WHEN 업로드 자리 발급 요청에 동의 값이 있으면, THE media-service SHALL 그 값을 영상의 동의로 저장한다. | US-1 |
| R-5 | THE media-service SHALL 영상 응답(상세, 목록, 업로드 자리 발급, 업로드 완료)에 영상의 동의 여부(`retentionConsent`)를 담는다. | US-1 |
| R-6 | WHEN 소유자가 "삭제"가 아닌 영상의 동의를 바꾸면, THE media-service SHALL 새 값을 저장하고 200과 영상 정보를 반환하며 이벤트는 발행하지 않는다. | US-3 |
| R-7 | IF 동의 변경 요청의 영상이 없거나 삭제됐거나 요청자가 소유자가 아니면, THEN THE media-service SHALL 404 `MEDIA_VIDEO_NOT_FOUND`를 반환한다. ADMIN도 남의 영상의 동의는 바꿀 수 없다. | US-3 |
| R-8 | WHEN 동의한 영상이 "삭제"로 바뀌면, THE media-service SHALL `video.deleted`에 보존 키(`retentionKey`)와 보존 만료 시각(`retainUntil`, 삭제 시각에서 1년 뒤)을 담는다. | US-1 |
| R-9 | WHEN 동의한 영상이 "삭제"로 바뀌면, THE media-service SHALL 그 영상의 sourceId·소유자·삭제 시각·보존 만료 시각만 담은 최소 기록을 같은 트랜잭션에서 남긴다. | US-1 |
| R-10 | WHEN 동의하지 않은 영상이 "삭제"로 바뀌면, THE media-service SHALL `video.deleted`에 보존 정보를 넣지 않고 최소 기록을 남기지 않는다. | US-2 |
| R-11 | THE media-service SHALL 보존 키를 비밀 키와 sourceId 문자열(소문자 UUID)의 HMAC-SHA256으로 계산해 16진 소문자 64자로 만든다. | US-1 |
| R-12 | IF 보존 키 비밀 키가 설정되지 않았거나 32바이트보다 짧으면, THEN THE media-service SHALL 기동에 실패한다. | US-1 |
| R-13 | WHEN 사용자가 보존 중인 삭제 영상 목록을 요청하면, THE media-service SHALL 요청자의 최소 기록을 삭제 시각 최신순으로 영상 ID·삭제 시각·보존 만료 시각만 담아 페이지 단위로 반환한다. | US-3 |
| R-14 | WHEN 소유자가 보존 중인 삭제 영상 하나의 철회를 요청하면, THE media-service SHALL 보존 키를 다시 계산해 `video.retention.revoked`를 발행 대상으로 기록하고, 같은 트랜잭션에서 최소 기록을 지우고 204를 반환한다. | US-3 |
| R-15 | IF 철회 요청의 최소 기록이 없거나(이미 철회, 만료, 동의하지 않은 영상 포함) 요청자가 소유자가 아니면, THEN THE media-service SHALL 404 `MEDIA_RETAINED_VIDEO_NOT_FOUND`를 반환한다. | US-3 |
| R-16 | WHEN 사용자가 전체 철회를 요청하면, THE media-service SHALL 요청자의 최소 기록마다 `video.retention.revoked`를 하나씩 발행 대상으로 기록하고 그 기록을 모두 지운 뒤 204를 반환한다. 기록이 없어도 204다. | US-3 |
| R-17 | WHEN 최소 기록의 보존 만료 시각이 지나면, THE media-service SHALL 24시간 안에 그 기록을 지우고 철회 이벤트는 발행하지 않는다. | US-1 |
| R-18 | THE media-service SHALL `video.retention.revoked`에 이벤트 ID, 영상 ID(`sourceId`), 소유자 ID(`ownerId`), 발생 시각, 보존 키를 담는다. | US-3 |

### 비기능 요구사항

| ID | 요구사항 |
| --- | --- |
| NFR-1 | THE media-service SHALL 보존 키 비밀 키를 로그, 응답, 이벤트에 남기지 않는다. |
| NFR-2 | THE media-service SHALL 보존 설정, 동의 변경, 보존 목록, 영상별 철회 요청의 p95 응답 시간을 300ms 이하로 유지한다. |
| NFR-3 | THE media-service SHALL 같은 영상에 철회 요청이 동시에 와도 `video.retention.revoked`를 한 번만 발행 대상으로 기록한다(여러 Pod 포함). |
| NFR-4 | THE media-service SHALL 철회가 확정되고 Kafka가 정상이면 10초 안에 이벤트를 발행한다. 다시 보낸 이벤트는 같은 이벤트 ID를 쓴다(SPEC-003 NFR-3과 같다). |

## 5. 영향 범위

| 레포 / 서비스 | 변경 개요 | 담당 요구사항 |
| --- | --- | --- |
| backend / media-service | 계정 기본값·영상 동의 저장과 API, 보존 키 계산, `video.deleted` 보존 정보, 최소 기록과 만료 정리, 철회 API와 이벤트 | R-1~R-18, NFR-1~NFR-4 |
| docs | 계약(`media-service.yaml`, `video.deleted`, `video.retention.revoked`, AsyncAPI), overview API·이벤트 표, 서비스 카탈로그, v4 전환 문서 D-7·F-2 | R-8, R-18 |
| docs / local | 로컬 compose의 `video.retention.revoked` 토픽, media-service 비밀 키 환경변수 예시 | R-12, R-14 |
| 영상 데이터를 가진 각 서비스 | (이후) 자기 데이터의 (b) 보존·만료·철회 처리. 각 서비스 spec. 그 전까지는 지금처럼 `video.deleted`에 모두 지우면 된다(보존 정보는 선택 필드). | — |
| ai / ai-gateway | 바뀌지 않는다. 호출 로그·결과 캐시는 모두 (a)라 지금처럼 지운다. | — |
| frontend | (이후) 동의 설정과 보존 목록 화면. 별도 spec | — |

## 6. 계약 변경

| 계약 파일 | 변경 | 하위호환 |
| --- | --- | --- |
| `service-contracts/openapi/media-service.yaml` | `GET · PUT /api/v1/media/retention-settings`, `PUT /api/v1/media/videos/{videoId}/retention-consent`, `GET · DELETE /api/v1/media/retained-videos`, `DELETE /api/v1/media/retained-videos/{videoId}` 추가. `CreateVideoRequest`에 선택 항목 `retentionConsent`, `VideoResponse`에 `retentionConsent`. 오류 코드 `MEDIA_RETAINED_VIDEO_NOT_FOUND` | 예(엔드포인트·선택 필드·응답 필드 추가) |
| `service-contracts/events/video.deleted.schema.json` | 선택 필드 `retention`(`retentionKey`, `retainUntil`). 없으면 보존하지 않는 영상이다. | 예(선택 필드 추가, `schemaVersion` 1 유지) |
| `service-contracts/events/video.retention.revoked.schema.json` | 새 이벤트 | 예(추가) |
| `service-contracts/asyncapi/media-service.yaml` | `video.retention.revoked` 채널·발행 | 예(추가) |

## 7. 성공 지표

- 로컬 compose에서 기본값을 "보존함"으로 바꾸고 영상을 올렸다가 지우면 `video.deleted`에 64자 보존 키가 실리고, 철회하면 같은 키의 `video.retention.revoked`가 한 번 나온다.
- 기본값을 바꾸지 않은 사용자의 영상을 지우면 `video.deleted`에 보존 정보가 없다.

## 8. 미결 사항

- 해당 없음
