---
id: SPEC-003
title: 영상 업로드와 관리
status: Implementing
owner: <이름>
repos: [backend, docs]
created: 2026-11-02
updated: 2026-11-03
related: [SPEC-001, ADR-0002, ADR-0005]
---

# SPEC-003 영상 업로드와 관리

> 이 문서에는 **무엇을, 왜**만 쓴다. 클래스, 테이블, 라이브러리 같은 구현 방법은 각 레포의 plan.md에 쓴다.

## 1. 배경과 목적

모든 분석은 사용자가 올린 영상 하나(source)에서 시작한다. 영상은 수백 MB에서 수 GB까지 크므로, 파일 바이트가 서비스를 거치지 않고 브라우저에서 저장소로 바로 올라가야 한다. media-service는 업로드할 자리를 발급하고, 업로드가 정말 끝났는지 확인한 뒤 "업로드 완료"를 한 번만 알린다. 이 알림(`video.uploaded`)이 이후 정규화와 분석 파이프라인의 출발점이 된다([아키텍처 개요](../../architecture/overview.md)의 분석 처리 흐름 1~2단계).

영상 삭제도 media-service에서 시작한다. 삭제 알림(`video.deleted`)을 받은 모든 서비스가 그 영상의 데이터를 지운다.

이 spec은 backend(media-service)를 먼저 구현한다. 업로드 화면은 이 계약을 기준으로 별도 frontend spec에서 만든다.

## 2. 범위

### 포함

- 업로드 자리 발급: 100MB 이하는 단일 업로드, 초과는 멀티파트 업로드
- 업로드 완료 확인과 "업로드 완료" 상태 전이, `video.uploaded` 발행
- 끝나지 않은 업로드의 만료(24시간)
- 내 영상 목록과 상세 조회
- 영상 삭제와 `video.deleted` 발행
- 소유자와 ADMIN 기준의 권한 확인
- REST 계약(`media-service.yaml`)과 이벤트 계약(`video.uploaded`, `video.deleted`)

### 제외

- 영상 정규화, 정규화 이후 상태(`NORMALIZING`, `READY`, `REJECTED`)와 사전 견적: normalize spec에서 다룬다.
- 저장소의 업로드 이벤트(S3 이벤트)로 업로드 완료를 처리하는 경로: infra 작업 때 추가한다. 이번에는 클라이언트의 완료 요청만 받는다.
- 업로드 화면(frontend): 별도 spec
- 영상 재생, 썸네일
- 사용자별 저장 용량·일일 처리량 상한

## 3. 사용자 시나리오

### US-1 작은 영상 업로드 (P1)

로그인한 사용자로서 100MB 이하의 영상을 올리고 싶다. 왜냐하면 영상을 분석하려면 먼저 올려야 하기 때문이다.

#### 인수 조건

- Given 로그인한 사용자, When 파일 이름·크기·형식으로 업로드 자리를 요청하면, Then 영상 ID와 단일 업로드용 주소를 받고 영상은 "업로드 중" 상태가 된다.
- Given 저장소에 파일을 다 올린 상태, When 업로드 완료를 요청하면, Then 영상은 "업로드 완료" 상태가 되고 `video.uploaded`가 한 번 발행된다.
- Given 파일을 올리지 않은 상태, When 업로드 완료를 요청하면, Then 업로드가 끝나지 않았다는 오류를 받고 상태는 그대로다.

### US-2 큰 영상 멀티파트 업로드 (P1)

로그인한 사용자로서 100MB가 넘는 영상을 조각으로 나눠 올리고 싶다. 왜냐하면 큰 파일을 한 번에 올리면 실패했을 때 처음부터 다시 올려야 하기 때문이다.

#### 인수 조건

- Given 로그인한 사용자, When 100MB를 넘는 파일로 업로드 자리를 요청하면, Then 조각 크기와 조각별 업로드 주소를 받는다.
- Given 모든 조각을 올린 상태, When 조각 목록과 함께 업로드 완료를 요청하면, Then 조각이 하나의 파일로 합쳐지고 영상은 "업로드 완료" 상태가 된다.

### US-3 내 영상 보기 (P1)

로그인한 사용자로서 내가 올린 영상 목록과 상태를 보고 싶다. 왜냐하면 어떤 영상이 올라갔고 어떤 영상이 실패했는지 알아야 하기 때문이다.

#### 인수 조건

- Given 영상을 여러 개 올린 사용자, When 목록을 요청하면, Then 내 영상만 최신순으로 받는다.
- Given 다른 사용자의 영상 ID, When 상세를 요청하면, Then 영상이 없다는 오류를 받는다.

### US-4 영상 삭제 (P2)

로그인한 사용자로서 내 영상을 지우고 싶다. 왜냐하면 더 이상 필요 없는 영상과 분석 결과가 남아 있지 않기를 원하기 때문이다.

#### 인수 조건

- Given 내 영상, When 삭제하면, Then 목록과 상세에서 사라지고 `video.deleted`가 한 번 발행된다.
- Given ADMIN, When 다른 사용자의 영상을 삭제하면, Then 삭제된다.

### US-5 끝나지 않은 업로드 정리 (P2)

운영자로서 업로드를 시작만 하고 끝내지 않은 영상이 저장소에 쌓이지 않기를 원한다. 왜냐하면 버려진 조각도 저장 비용이 들기 때문이다.

#### 인수 조건

- Given "업로드 중" 상태로 24시간이 지난 영상, When 정리 시점이 되면, Then 영상은 "만료" 상태가 되고 올라간 조각은 지워진다.

## 4. 요구사항

### 기능 요구사항 (EARS)

| ID | 요구사항 | 시나리오 |
| --- | --- | --- |
| R-1 | WHEN 인증된 사용자가 파일 이름, 크기, 형식으로 업로드 자리를 요청하면, THE media-service SHALL 요청자를 소유자로 하는 영상을 "업로드 중"(`UPLOADING`) 상태로 만들고 201과 영상 ID를 반환한다. | US-1, US-2 |
| R-2 | WHERE 요청한 파일 크기가 100MB 이하인 경우, THE media-service SHALL 신고한 크기와 다른 파일을 저장소가 거절하는 단일 업로드 주소를 반환한다. | US-1 |
| R-3 | WHERE 요청한 파일 크기가 100MB를 넘는 경우, THE media-service SHALL 멀티파트 업로드를 시작하고 조각 크기와 조각별 업로드 주소를 반환한다. | US-2 |
| R-4 | IF 요청한 파일 크기가 0이거나 5GB를 넘으면, THEN THE media-service SHALL 400과 오류 코드 `MEDIA_FILE_SIZE_INVALID`를 반환한다. | US-1, US-2 |
| R-5 | IF 요청한 파일 형식이 mp4, mov, mkv, avi(확장자와 MIME 형식 모두)가 아니면, THEN THE media-service SHALL 400과 오류 코드 `MEDIA_UNSUPPORTED_FORMAT`을 반환한다. | US-1, US-2 |
| R-6 | THE media-service SHALL 저장소의 파일 경로를 영상 ID로만 만들고 사용자가 보낸 파일 이름을 경로에 쓰지 않는다. | US-1, US-2 |
| R-7 | WHEN 소유자가 "업로드 중"인 영상의 업로드 완료를 요청하고 저장소에 신고한 크기의 파일이 있으면, THE media-service SHALL 영상을 "업로드 완료"(`UPLOADED`)로 바꾸고 200과 영상 정보를 반환한다. | US-1 |
| R-8 | WHEN 소유자가 멀티파트 영상의 업로드 완료를 조각 번호와 조각 확인값 목록과 함께 요청하면, THE media-service SHALL 조각을 하나의 파일로 합친 뒤 R-7과 같이 처리한다. | US-2 |
| R-9 | WHEN 영상이 "업로드 완료"로 바뀌면, THE media-service SHALL 상태 변경과 함께 `video.uploaded` 이벤트를 한 번 발행 대상으로 기록한다. | US-1, US-2 |
| R-10 | IF 업로드 완료 요청 시점에 저장소에 파일이 없거나 크기가 신고한 크기와 다르면, THEN THE media-service SHALL 409와 오류 코드 `MEDIA_UPLOAD_INCOMPLETE`를 반환하고 상태를 바꾸지 않는다. | US-1 |
| R-11 | IF 이미 "업로드 완료"인 영상에 업로드 완료 요청이 다시 오면, THEN THE media-service SHALL 상태를 바꾸지 않고 이벤트를 다시 발행하지 않으며 200과 현재 영상 정보를 반환한다. | US-1, US-2 |
| R-12 | IF "만료" 또는 "삭제" 상태인 영상에 업로드 완료 요청이 오면, THEN THE media-service SHALL 409와 오류 코드 `MEDIA_INVALID_STATE`를 반환한다. | US-1, US-5 |
| R-13 | WHEN 영상이 "업로드 중" 상태로 24시간을 넘기면, THE media-service SHALL 영상을 "만료"(`EXPIRED`)로 바꾸고 저장소에 올라간 파일과 끝나지 않은 조각을 지운다. | US-5 |
| R-14 | WHEN 인증된 사용자가 영상 목록을 요청하면, THE media-service SHALL 요청자가 소유한 영상 중 "삭제" 상태가 아닌 것을 만든 시각 최신순으로 한 페이지(기본 20개, 최대 100개)씩 반환한다. | US-3 |
| R-15 | WHEN 인증된 사용자가 볼 수 있는 영상의 상세를 요청하면, THE media-service SHALL 영상 ID, 파일 이름, 크기, 형식, 상태, 만든 시각, 업로드 완료 시각을 반환한다. | US-3 |
| R-16 | IF 요청한 영상이 없거나, "삭제" 상태이거나, 요청자가 소유자도 ADMIN도 아니면, THEN THE media-service SHALL 세 경우를 구분하지 않고 404와 오류 코드 `MEDIA_VIDEO_NOT_FOUND`를 반환한다. | US-3, US-4 |
| R-17 | WHERE 요청자가 ADMIN인 경우, THE media-service SHALL 다른 사용자의 영상도 상세 조회와 삭제를 허용한다. | US-4 |
| R-18 | WHEN 소유자나 ADMIN이 "삭제" 상태가 아닌 영상의 삭제를 요청하면, THE media-service SHALL 영상을 "삭제"(`DELETED`)로 바꾸고 204를 반환한다. | US-4 |
| R-19 | WHEN 영상이 "삭제"로 바뀌면, THE media-service SHALL 상태 변경과 함께 `video.deleted` 이벤트를 한 번 발행 대상으로 기록한다. | US-4 |
| R-20 | WHEN 영상이 "삭제"로 바뀌면, THE media-service SHALL 저장소에서 그 영상 ID 아래의 파일과 끝나지 않은 조각을 지운다. | US-4 |
| R-21 | THE media-service SHALL `video.uploaded`와 `video.deleted`에 이벤트 ID, 영상 ID(`sourceId`), 소유자 ID(`ownerId`), 발생 시각을 담고, `video.uploaded`에는 저장 경로, 크기, 형식을 더한다. | US-1, US-4 |

### 비기능 요구사항

| ID | 요구사항 |
| --- | --- |
| NFR-1 | THE media-service SHALL 영상 파일 바이트를 직접 받거나 전달하지 않는다. 업로드는 브라우저에서 저장소로 바로 간다. |
| NFR-2 | THE media-service SHALL 같은 영상에 업로드 완료 요청이 동시에 10건 와도 상태를 한 번만 바꾸고 `video.uploaded`를 한 번만 발행 대상으로 기록한다(여러 Pod 포함). |
| NFR-3 | THE media-service SHALL 상태 변경이 확정되고 Kafka가 정상이면 10초 안에 이벤트를 발행한다. 발행이 실패하면 다시 시도하고, 다시 보낸 이벤트는 같은 이벤트 ID를 쓴다. |
| NFR-4 | THE media-service SHALL 업로드 자리 발급, 업로드 완료, 목록, 상세 요청의 p95 응답 시간을 300ms 이하로 유지한다(저장소의 조각 합치기 시간 제외). |
| NFR-5 | THE media-service SHALL 업로드 주소(서명 포함)와 파일 내용을 로그에 남기지 않는다. |
| NFR-6 | THE media-service SHALL 업로드 주소를 1시간 동안만 유효하게 발급한다. |

## 5. 영향 범위

| 레포 / 서비스 | 변경 개요 | 담당 요구사항 |
| --- | --- | --- |
| backend / media-service | 새 서비스 모듈. 업로드 자리 발급, 완료 확인, 만료, 목록·상세, 삭제, 이벤트 발행 | R-1~R-21, NFR-1~NFR-6 |
| backend / api-gateway | 변경 없음. `/api/v1/media/**` 라우트는 SPEC-001에서 이미 만들었다. | — |
| docs / `local/` | 로컬 compose에 media-service, Kafka, S3 호환 저장소(SeaweedFS) 추가 | — |
| infra | 운영 S3 버킷과 권한은 infra 작업 때 추가한다(이번 spec 범위 밖). | — |
| frontend | 이번 spec에서는 변경 없음. 업로드 화면은 별도 spec | — |

## 6. 계약 변경

| 계약 파일 | 변경 | 하위호환 |
| --- | --- | --- |
| `docs/contracts/openapi/media-service.yaml` | 신규: 업로드 자리 발급, 업로드 완료, 목록, 상세, 삭제 (`/api/v1/media/videos/**`) | 해당 없음 (신규) |
| `docs/contracts/asyncapi/media-service.yaml` | 신규: `video.uploaded`, `video.deleted` 발행 | 해당 없음 (신규) |
| `docs/contracts/events/video.uploaded.schema.json`, `video.deleted.schema.json` | 신규: 이벤트 payload JSON Schema | 해당 없음 (신규) |

## 7. 성공 지표

- 로컬 compose에서 100MB 이하 파일과 100MB 초과 파일을 각각 올리고, 완료 요청 뒤 Kafka에서 `video.uploaded`를 한 번씩 확인할 수 있다.
- 같은 영상에 완료 요청을 동시에 보내도 `video.uploaded`가 한 번만 나온다(NFR-2 테스트).
- R-1~R-21 각각에 대응하는 자동화 테스트가 통과한다.

## 8. 미결 사항

- 없음. 결정 사항(2026-11-02 사용자 확인)
  - 범위는 업로드·완료·목록·삭제까지다. 사전 견적과 정규화 이후 상태는 normalize spec에서 다룬다.
  - 파일은 최대 5GB, mp4·mov·mkv·avi를 받는다. 100MB 이하는 단일 업로드, 초과는 멀티파트다.
  - "업로드 중"으로 24시간이 지나면 만료한다.
  - 조회와 삭제는 소유자와 ADMIN만 할 수 있다.
