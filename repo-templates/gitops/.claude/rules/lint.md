---
paths:
  - ".yamllint"
  - ".kube-linter.yaml"
---

# lint 설정 (gitops)

검사 예외(무시 주석)의 형식은 루트 AGENTS.md의 "검사 예외 (무시 주석)"를 따른다.

| 도구 | 설정 | 검사 내용 |
| --- | --- | --- |
| yamllint | `.yamllint` | YAML 문법, 들여쓰기, 중복 키 |
| kubeconform | CRD 스키마 카탈로그(datreeio/CRDs-catalog) 추가 | Kubernetes·CRD 스키마. `Application`, `ApplicationSet`, `ExternalSecret`까지 검사한다 |
| kube-linter | `.kube-linter.yaml` | `resources` 누락, probe 누락, `runAsNonRoot` 아님, `latest` 태그, 권한 상승 허용 등 이 레포의 매니페스트 규칙 |

- kubeconform에 `-ignore-missing-schemas`를 쓰지 않는다. 카탈로그에 없는 CRD는 스키마를 레포에 추가한다.

## 설정 단위 예외 (이 목록만 허용)
- 없음. kube-linter 예외는 리소스 annotation으로 쓴다.
