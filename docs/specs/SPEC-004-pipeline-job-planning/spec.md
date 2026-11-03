---
id: SPEC-004
title: Pipeline 청크 구간 계산과 작업 계획 저장
status: Implementing
owner: backend 담당자
repos: [backend]
created: 2026-11-02
updated: 2026-11-03
related: [ADR-0002, ADR-0005]
---

# SPEC-004 Pipeline 청크 구간 계산과 작업 계획 저장

## 1. 배경과 목적

Pipeline은 정규화한 영상의 처리 구간을 계획한다. AI팀과 이벤트 계약을 확정하기 전에, 영상 길이와 처리 프로필을 이용한 계산 및 계획의 영속성을 독립적으로 검증한다. 근거는 [아키텍처 개요](../../architecture/overview.md)의 청크 계획과 [ADR-0005](../../adr/0005-search-and-event-paths.md)다. PRD의 에픽은 아직 정의되지 않았다.

## 2. 범위

### 포함

- 내부 유스케이스를 통한 Job과 소속 Chunk 계획 생성 및 DB 저장
- 정규화 사본의 PTS 기준 영상 길이와 처리 프로필에 따른 청크 계산
- 소유 구간과 앞뒤 겹침을 포함한 확장 구간 구분
- 계획 생성의 원자성 및 저장 결과 재조회 검증
- 계획 식별자에 따른 중복 요청 처리와 영상당 활성 Job 1개 제한

### 제외

- Kafka 소비·발행, Outbox, 외부 이벤트 payload와 ID 직렬화 형식
- 작업 배정, 공정성 스케줄러, 실행 상태 전이, 완료 판정
- 외부 HTTP API와 frontend 변경
- AI 호출, 벡터 차원, 분석 결과 저장
- 운영 배포와 infra·gitops 변경

## 3. 사용자 시나리오

### US-1 영상의 처리 구간 계획 (P1)

backend 개발자로서 외부 이벤트 없이 영상 길이에 맞는 처리 구간을 계산하고 싶다. 경계 누락과 중복 없이 이후 청크 처리에 연결하기 위해서다.

#### 인수 조건

- Given 250초 영상과 청크 120초·겹침 5초 프로필, When 계획하면, Then 소유 구간은 0~120, 120~240, 240~250초이고 확장 구간은 0~125, 115~245, 235~250초다.
- Given 청크 길이의 정확한 배수인 영상, When 계획하면, Then 길이가 0인 마지막 청크를 만들지 않는다.
- Given 영상 길이가 청크 길이보다 짧음, When 계획하면, Then 영상 전체를 소유하는 청크 하나를 만든다.

### US-2 계산한 계획 보존 (P1)

backend 개발자로서 Job과 모든 Chunk 계획을 함께 저장하고 싶다. 외부 워커 없이도 계획을 다시 읽고 계산 결과와 비교하기 위해서다.

#### 인수 조건

- Given 유효한 계획 입력, When 저장 후 별도 트랜잭션에서 다시 읽으면, Then Job의 입력과 Chunk의 순서·구간이 보존된다.
- Given Chunk 저장 도중 실패, When 트랜잭션이 끝나면, Then 해당 요청의 Job과 Chunk는 하나도 남지 않는다.

### US-3 중복 요청과 활성 작업 보호 (P1)

backend 개발자로서 계획 생성을 재시도해도 중복 Job을 만들지 않고 싶다. 다른 계획 식별자로 요청하더라도 같은 영상의 활성 작업을 중복 실행하지 않기 위해서다.

#### 인수 조건

- Given 같은 계획 식별자와 같은 입력, When 다시 생성 요청하면, Then 기존 Job과 Chunk 계획을 반환하고 새로 저장하지 않는다.
- Given 같은 계획 식별자와 다른 입력, When 생성 요청하면, Then 기존 계획을 변경하지 않고 거절한다.
- Given 같은 영상에 활성 Job이 있음, When 다른 계획 식별자로 생성 요청하면, Then 추가 Job을 생성하지 않고 거절한다.
- Given 같은 영상에 활성 Job이 없음, When 새로운 계획 식별자로 생성 요청하면, Then 새 Job과 Chunk 계획을 저장한다.
- Given 같은 영상의 서로 다른 계획 생성 요청이 동시에 도착함, When 처리가 끝나면, Then 활성 Job은 최대 1개다.

## 4. 요구사항

이 문서는 사용자와 확정한 정책을 구현 기준으로 사용한다. ADR-0007에 따라 명세 확정은 별도 팀원 Approve를 요구하지 않는다. 구간은 시작 포함·끝 제외로 해석하고, 영상의 최종 끝은 전체 길이와 같다. 내부 시간 표현은 외부 메시지 계약을 정하지 않는 범위에서 plan에 명시한다.

계획 식별자는 호출자가 지정하며 pipeline-service 내에서 하나의 계획을 식별한다. 같은 입력은 sourceId, 정규화 사본의 영상 길이, 선택한 처리 프로필과 실제 적용한 청크 길이·겹침 길이가 모두 같은 경우다. 비교에 필요한 입력은 저장 후 재사용하며 외부 이벤트 형식은 확정하지 않는다.

활성 Job은 기존 아키텍처의 `PLANNED`, `RUNNING`, `ANALYZED` 상태다. `COMPLETED`, `COMPLETED_WITH_ERRORS`, `TIMED_OUT`, `CANCELLED`는 종료 상태다. 이번 생성 기능은 `PLANNED` Job을 만들며 상태 전이·종료 API는 구현하지 않는다. 종료 상태 이후 새 계획 허용은 저장소 통합 테스트의 종료 상태 데이터로 검증한다.

동일 계획 식별자의 재요청 판정을 영상의 활성 Job 검사보다 먼저 한다. 기존 계획 재조회는 Job의 활성 여부와 무관하게 동작하며, 기존 계획을 다시 활성화하지 않는다.

### 기능 요구사항 (EARS)

| ID | 요구사항 | 시나리오 |
| --- | --- | --- |
| R-1 | WHEN 기본 운영 프로필로 계획하면, THE pipeline-service SHALL 영상이 600초 미만이면 60초, 7200초 초과이면 180초, 나머지는 120초를 소유 구간의 최대 길이로 선택한다. | US-1 |
| R-2 | WHEN 로컬 기본 프로필로 계획하면, THE pipeline-service SHALL 소유 구간의 최대 길이를 60초로 선택한다. | US-1 |
| R-3 | WHEN 유효한 영상 길이와 프로필로 계획하면, THE pipeline-service SHALL 0부터 영상 끝까지 빈틈과 중복 없이 이어지는 소유 구간을 계산한다. | US-1 |
| R-4 | WHEN 소유 구간을 계산하면, THE pipeline-service SHALL 길이가 0인 청크를 생성하지 않는다. | US-1 |
| R-5 | WHEN 확장 구간을 계산하면, THE pipeline-service SHALL 소유 구간 앞뒤에 프로필의 겹침 길이를 적용하되 영상의 시작과 끝을 넘지 않게 한다. | US-1 |
| R-6 | WHEN 기본 프로필로 확장 구간을 계산하면, THE pipeline-service SHALL 겹침 길이로 5초를 사용한다. | US-1 |
| R-7 | IF 영상 길이 또는 청크 길이가 0 이하이거나 겹침 길이가 음수이면, THEN THE pipeline-service SHALL 계획 생성을 거절한다. | US-1 |
| R-8 | WHEN 유효한 계획을 저장하면, THE pipeline-service SHALL 해당 Job의 계획 입력을 보존한다. | US-2 |
| R-9 | WHEN 유효한 계획을 저장하면, THE pipeline-service SHALL 소속 Chunk 각각의 순서와 소유·확장 구간을 보존한다. | US-2 |
| R-10 | IF Job 또는 Chunk 저장 중 하나라도 실패하면, THEN THE pipeline-service SHALL 해당 계획 생성의 모든 저장을 취소한다. | US-2 |
| R-11 | WHEN 저장한 계획을 재조회하면, THE pipeline-service SHALL Chunk를 계획 순서대로 제공한다. | US-2 |
| R-12 | WHEN 같은 계획 식별자와 같은 입력으로 재요청하면, THE pipeline-service SHALL 새 Job·Chunk를 저장하지 않고 기존 계획을 반환한다. | US-3 |
| R-13 | IF 같은 계획 식별자로 다른 입력을 요청하면, THEN THE pipeline-service SHALL 기존 계획을 변경하지 않고 요청을 거절한다. | US-3 |
| R-14 | IF 같은 영상에 활성 Job이 있고 새로운 계획 식별자로 요청하면, THEN THE pipeline-service SHALL 추가 Job을 생성하지 않고 요청을 거절한다. | US-3 |
| R-15 | WHEN 같은 영상에 활성 Job이 없고 새로운 계획 식별자로 유효한 요청을 받으면, THE pipeline-service SHALL 새 Job과 Chunk 계획을 저장한다. | US-3 |
| R-16 | WHEN 동일 계획 식별자와 같은 입력의 요청을 동시에 받으면, THE pipeline-service SHALL 하나의 Job·Chunk 계획만 저장하고 성공한 요청들에 같은 계획을 반환한다. | US-3 |
| R-17 | WHEN 같은 영상의 서로 다른 계획 식별자 요청을 동시에 받으면, THE pipeline-service SHALL 해당 영상의 활성 Job을 최대 1개만 저장한다. | US-3 |

### 비기능 요구사항

| ID | 요구사항 |
| --- | --- |
| NFR-1 | THE pipeline-service SHALL R-1~R-17 각각을 검증하는 자동화 테스트를 하나 이상 제공한다. |
| NFR-2 | THE pipeline-service SHALL 계획 계산·저장 검증에서 외부 AI 호출과 Kafka 연결을 각각 0회 수행한다. |

## 5. 영향 범위

| 레포 / 서비스 | 변경 개요 | 담당 요구사항 |
| --- | --- | --- |
| backend / pipeline-service | 청크 계획 내부 유스케이스, 서비스 소유 DB 저장, 마이그레이션, 계산·저장 테스트 | R-1~R-17, NFR-1~NFR-2 |
| docs | 기능 명세와 목록 | 해당 없음 |

기존 배포 단위의 책임을 구현하며 서비스 경계를 추가하지 않는다. 구체적인 스키마·의존성·빌드 구성은 승인된 spec 이후 plan에서 검토한다.

## 6. 계약 변경

| 계약 파일 | 변경 | 하위호환 |
| --- | --- | --- |
| 해당 없음 | 외부 API·이벤트를 추가하거나 변경하지 않음 | 해당 없음 |

## 7. 성공 지표

- 600초·7200초의 직전·정확한 경계·직후를 포함한 기본 프로필 테스트 통과
- 짧은 영상·정확한 배수·잔여 구간·잘못된 입력 테스트 통과
- 실제 PostgreSQL에서 재조회 및 저장 실패 시 전체 롤백 검증 통과
- 동일 식별자 재시도·입력 충돌·다른 식별자의 활성 Job 충돌·동시 요청·종료 후 새 계획 생성 테스트 통과
- pipeline-service 빌드 및 Spotless 검사 통과

## 8. 미결 사항

- 요구사항의 미결 사항은 없음. 중복 생성 정책은 2026-11-03 사용자 결정으로 명확화했다.
- PR #29는 초안 그대로 머지되었으며 승인 리뷰·댓글·인라인 댓글이 없었다. 이번 정책이 기존 리뷰에서 승인됐다고 기록하지 않는다.
- R-12~R-17, 활성 상태 구분, 동일 입력 기준과 구간·입력 검증은 사용자와 확정했다. PR #36 머지 후 사용자 지시로 구현을 진행했으며, ADR-0007 정책에 따라 상태를 Approved로 정리한다. GitHub 승인 리뷰 이력은 추가하지 않는다.
- SPEC-003은 영상 업로드이며 Pipeline 계획은 SPEC-004다. 구현 추적은 backend #32를 재사용한다.

- backend PR #33의 내부 계획 구현은 머지됐다. 필수 CI와 로컬 전체 309개 테스트(IDE DEBUG 환경변수 제거)가 통과했다. 운영 배포는 범위 밖이므로 Done이 아닌 Implementing으로 추적한다.
