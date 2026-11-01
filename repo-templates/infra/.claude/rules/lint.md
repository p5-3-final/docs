---
paths:
  - ".tflint.hcl"
  - ".trivyignore"
---

# lint 설정 (infra)

검사 예외(무시 주석)의 형식은 루트 AGENTS.md의 "검사 예외 (무시 주석)"를 따른다.

| 도구 | 설정 | 검사 내용 |
| --- | --- | --- |
| `terraform fmt` | — | 포맷 |
| tflint | 레포 루트 `.tflint.hcl` | `terraform` plugin `preset = "recommended"` + `terraform_documented_variables`, `terraform_documented_outputs`, `terraform_naming_convention`, `terraform_standard_module_structure` / `aws` plugin (잘못된 인스턴스 타입 등) |
| trivy config | — | 보안 설정 (공개 S3, 암호화 누락, 과도한 IAM·보안 그룹) |

## 설정 단위 예외 (이 목록만 허용)
- 없음. 규칙 예외는 해당 줄에 무시 주석으로 쓴다.
