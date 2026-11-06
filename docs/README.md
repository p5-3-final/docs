# 문서 지도

| 문서 | 언제 읽나 | 누가 고치나 |
| --- | --- | --- |
| [handoff.md](handoff.md) | 새 컴퓨터·새 세션에서 작업을 이어받을 때 가장 먼저 | 상태가 바뀔 때마다 |
| [principles.md](principles.md) | 모든 plan 작성 전 | 팀 합의 + ADR |
| [product/prd.md](product/prd.md) | 기능을 기획할 때 | PM 역할 |
| [product/glossary.md](product/glossary.md) | 도메인 용어가 헷갈릴 때 | 누구나 |
| [architecture/architecture.md](architecture/architecture.md) | 아키텍처 v5.1 단일 기준. 업로드·실시간 통합 파이프라인, 토픽, AI 호출, 완료 판정, 비용. 브라우저로 보려면 같은 폴더의 `architecture.html` | 구조·계약·spec을 바꾸기 전에 먼저 고치고 `scripts/render-architecture-html.sh`로 html을 같이 갱신한다 |
| [architecture/processing-flow.md](architecture/processing-flow.md) | 업로드 후 처리 순서·토픽·AI 호출·AI 담당자 교체 지점을 한 장으로 확인 | 처리 흐름이나 AI 호출 자리가 바뀔 때 |
| [architecture/service-catalog.md](architecture/service-catalog.md) | 서비스 담당자, 포트, DB 확인 | 서비스 추가·변경 시 |
| [architecture/delivery-and-data.md](architecture/delivery-and-data.md) | 무엇을 어디에 올리고 어떻게 배포·보관·삭제하는지 확인 | 배포 흐름이나 저장 위치가 바뀔 때 |
| [architecture/legacy/](architecture/legacy/overview.md) | 대체된 옛 개요(v3·v4), v4 전환 목록, 설계 원본(`design-origin-v2.md`·`.html`). 참고용 | 읽지 않아도 된다 |
| [specs/](specs/README.md) | 기능 구현 전 | 기능 담당자 |
| [contracts/](../service-contracts/README.md) | API·이벤트 연동 시 | 생산자 서비스 담당자 |
| [adr/](adr/README.md) | "왜 이렇게 했지?"가 궁금할 때 | 결정한 사람 |
| [templates/](templates) | 새 문서를 만들 때 | 거의 안 바뀜 |

## SDD 산출물 흐름

```mermaid
flowchart LR
  C[principles.md] -.검증 기준.-> P
  PRD[product/prd.md] --> S["spec.md<br/>(루트 docs/specs)"]
  S --> K["contracts/<br/>OpenAPI·AsyncAPI"]
  S --> P["plan.md<br/>(각 레포 specs/)"]
  K --> P
  P --> T["tasks.md<br/>(각 레포 specs/)"]
  T --> I[코드 + 테스트]
  P -.중요 결정.-> A[adr/]
```
