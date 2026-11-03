---
id: SPEC-006
title: 원본 영상 재생
status: Implementing
owner: <이름>
repos: [backend, frontend, docs]
created: 2026-11-03
updated: 2026-11-03
related: [SPEC-003, SPEC-005, ADR-0006]
---

# SPEC-006 원본 영상 재생

> 이 문서에는 **무엇을, 왜**만 쓴다. 클래스, 테이블, 라이브러리 같은 구현 방법은 각 레포의 plan.md에 쓴다.

## 1. 배경과 목적

SPEC-003·SPEC-005로 영상을 올리고 목록에서 상태를 볼 수 있게 됐지만, 올린 영상을 다시 볼 방법이 없다. 사용자는 분석과 상관없이 자기가 올린 영상이 맞는지, 어떤 장면이 담겼는지 바로 확인할 수 있어야 한다.

이 spec은 업로드한 **원본 파일**을 브라우저에서 재생하는 기능을 정한다. 분석 결과 화면의 플레이어는 정규화 사본을 기준으로 하며([아키텍처 개요](../../architecture/overview.md)의 "시간 기준") 이 spec과 별개다. 원본도 업로드처럼 파일 바이트가 서비스를 거치지 않고, media-service가 주는 짧게 유효한 서명 주소로 브라우저가 저장소에서 바로 읽는다.

## 2. 범위

### 포함

- media-service: 원본 재생·내려받기 주소 발급 API(계약 추가)
- frontend: 영상 상세 화면(파일 정보와 플레이어), 목록에서 상세로 이동, 상세에서 삭제
- 브라우저가 재생할 수 없는 형식의 안내와 원본 내려받기
- 재생 중 주소가 만료되면 새 주소로 이어서 재생

### 제외

- 정규화 사본 재생, 분석 결과 오버레이·타임라인: 분석 결과 화면 spec
- 썸네일, 미리보기 이미지
- 스트리밍 형식 변환(HLS 등), 화질 선택
- 재생 위치 저장, 재생 기록

## 3. 사용자 시나리오

### US-1 내 영상 재생 (P1)

로그인한 사용자로서 내가 올린 영상을 다시 보고 싶다. 왜냐하면 분석하기 전에 올바른 영상을 올렸는지 확인하고 싶기 때문이다.

#### 인수 조건

- Given 업로드가 끝난 내 영상, When 목록에서 영상 이름을 누르면, Then 상세 화면에서 파일 정보와 함께 영상이 재생된다.
- Given 상세 화면의 주소, When 새로고침하거나 주소를 다시 열면, Then 같은 영상의 상세 화면이 열린다.
- Given 1시간보다 긴 영상을 보는 중, When 재생 주소가 만료되면, Then 보던 위치부터 이어서 재생된다.

### US-2 재생할 수 없는 영상 (P1)

로그인한 사용자로서 재생할 수 없는 영상이면 왜 안 되는지 알고 싶다.

#### 인수 조건

- Given 업로드가 끝나지 않았거나 만료된 영상, When 상세 화면을 열면, Then 재생할 수 없는 이유가 보이고 플레이어는 없다.
- Given 브라우저가 지원하지 않는 형식이나 코덱의 영상, When 재생하면, Then 이 브라우저에서 재생할 수 없다는 안내와 원본 내려받기 버튼이 보인다.
- Given 없거나 지워졌거나 남의 영상 주소, When 상세 화면을 열면, Then 영상을 찾을 수 없다는 안내와 목록으로 돌아가는 링크가 보인다.

### US-3 상세에서 삭제 (P2)

로그인한 사용자로서 영상을 보다가 필요 없으면 그 자리에서 지우고 싶다.

#### 인수 조건

- Given 상세 화면, When 삭제를 누르고 확인하면, Then 영상이 지워지고 목록 화면으로 돌아간다.

## 4. 요구사항

### 기능 요구사항 (EARS)

| ID | 요구사항 | 시나리오 |
| --- | --- | --- |
| R-1 | WHEN 소유자나 ADMIN이 업로드 완료 이후 상태(`UPLOADED`, `NORMALIZING`, `READY`, `REJECTED`)인 영상의 재생 주소를 요청하면, THE media-service SHALL 원본 파일을 읽을 수 있는 재생 주소, 원래 파일 이름으로 내려받는 주소, 두 주소의 만료 시각을 반환한다. | US-1, US-2 |
| R-2 | THE media-service SHALL 재생 주소와 내려받기 주소를 발급 시점부터 1시간 동안만 유효하게 서명한다. | US-1 |
| R-3 | THE media-service SHALL 재생 주소로 받는 응답의 형식(Content-Type)을 업로드 때 신고한 영상 형식으로 한다. | US-1 |
| R-4 | IF 재생 주소를 요청한 영상이 `UPLOADING` 또는 `EXPIRED`이면, THEN THE media-service SHALL 409와 오류 코드 `MEDIA_NOT_PLAYABLE`을 반환한다. | US-2 |
| R-5 | IF 재생 주소를 요청한 영상이 없거나, "삭제" 상태이거나, 요청자가 소유자도 ADMIN도 아니면, THEN THE media-service SHALL 세 경우를 구분하지 않고 404와 오류 코드 `MEDIA_VIDEO_NOT_FOUND`를 반환한다(SPEC-003 R-16과 같다). | US-2 |
| R-6 | WHEN 사용자가 내 영상 목록에서 영상 이름을 누르면, THE frontend SHALL 그 영상의 상세 화면으로 이동한다. 상세 화면은 영상마다 고유한 주소를 갖는다. | US-1 |
| R-7 | WHEN 사용자가 상세 화면에 들어오면, THE frontend SHALL 파일 이름, 크기, 형식, 상태, 올린 시각, 업로드 완료 시각을 표시한다. | US-1 |
| R-8 | WHILE 영상이 업로드 완료 이후 상태이면, THE frontend SHALL 상세 화면에 재생 주소로 영상을 재생하는 플레이어를 표시한다. | US-1 |
| R-9 | WHILE 영상이 `UPLOADING` 또는 `EXPIRED`이면, THE frontend SHALL 플레이어 대신 재생할 수 없는 이유를 표시한다. | US-2 |
| R-10 | IF 브라우저가 영상을 재생하지 못하면(지원하지 않는 형식·코덱), THEN THE frontend SHALL 이 브라우저에서 재생할 수 없다는 안내와 원본 내려받기 버튼을 표시한다. | US-2 |
| R-11 | IF 재생 중 재생 주소가 만료되어 영상을 읽지 못하면, THEN THE frontend SHALL 새 재생 주소를 한 번 받아 보던 위치부터 이어서 재생한다. | US-1 |
| R-12 | IF 상세 화면의 영상 응답이 `MEDIA_VIDEO_NOT_FOUND`이면, THEN THE frontend SHALL 영상을 찾을 수 없다는 안내와 목록으로 돌아가는 링크를 표시한다. | US-2 |
| R-13 | WHEN 사용자가 상세 화면에서 삭제를 확인하고 삭제가 성공하면, THE frontend SHALL 내 영상 목록 화면으로 이동한다(확인 창은 SPEC-005 R-19와 같다). | US-3 |

### 비기능 요구사항

| ID | 요구사항 |
| --- | --- |
| NFR-1 | THE media-service SHALL 영상 바이트를 직접 내보내지 않는다. 재생과 내려받기는 브라우저가 저장소에서 바로 읽는다. |
| NFR-2 | THE media-service SHALL 재생 주소 발급 요청의 p95 응답 시간을 300ms 이하로 유지한다. |
| NFR-3 | THE media-service와 THE frontend SHALL 재생·내려받기 주소(서명 포함)를 로그, 브라우저 저장소(localStorage, sessionStorage, IndexedDB), 콘솔에 남기지 않는다. |
| NFR-4 | THE frontend SHALL 상세 화면의 플레이어, 내려받기, 삭제를 키보드만으로 조작할 수 있게 한다. |
| NFR-5 | THE frontend SHALL 가로 360px 이상의 모든 화면 너비에서 가로 스크롤 없이 상세 화면을 표시하고, 플레이어는 화면 너비에 맞춰 영상 비율을 유지한다. |

## 5. 영향 범위

| 레포 / 서비스 | 변경 개요 | 담당 요구사항 |
| --- | --- | --- |
| backend / media-service | 재생·내려받기 주소 발급 API, 상태·권한 확인 | R-1~R-5, NFR-1~NFR-3 |
| frontend | 영상 상세 화면과 플레이어, 목록에서 이동, 재생 불가 안내, 주소 만료 시 이어 재생, 상세에서 삭제 | R-6~R-13, NFR-3~NFR-5 |
| docs | 계약 추가. 로컬 SeaweedFS가 브라우저의 교차 출처 GET·Range 요청을 허용하는지 확인한다. | — |
| infra | (이후) 운영 S3 버킷 CORS에 GET 허용 추가. 사용자 지시 시 진행한다. | — |

## 6. 계약 변경

| 계약 파일 | 변경 | 하위호환 |
| --- | --- | --- |
| `docs/contracts/openapi/media-service.yaml` | `GET /api/v1/media/videos/{videoId}/playback`(operationId `getVideoPlayback`) 추가: 200 `VideoPlayback{url, downloadUrl, expiresAt}`, 409 `MEDIA_NOT_PLAYABLE`, 404 `MEDIA_VIDEO_NOT_FOUND`. 1.0.1 → 1.1.0 | 예(엔드포인트·오류 코드 추가) |

## 7. 성공 지표

- 로컬 compose와 frontend로 mp4 영상을 올린 뒤 상세 화면에서 재생하고, 재생할 수 없는 형식은 안내와 내려받기를 시연할 수 있다.
- 휴대폰(360px)과 데스크톱에서 상세 화면과 재생을 쓸 수 있다.

## 8. 미결 사항

- 없음. 결정 사항(2026-11-03 사용자 확인)
  - 분석과 별개로 원본을 재생한다.
  - 재생은 영상 상세 화면에서 한다(목록 위 팝업이 아님).
  - 브라우저가 재생하지 못하면 안내와 원본 내려받기를 보여 준다.
  - 재생 주소는 1시간 유효하다.
  - 업로드 완료 이후 상태(`UPLOADED`, `NORMALIZING`, `READY`, `REJECTED`)를 재생할 수 있다. 권한은 상세 조회와 같이 소유자와 ADMIN이다.
