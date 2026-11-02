# 접근 토큰 계약

auth-service가 발급하고 api-gateway가 검증하는 접근 토큰의 형식이다(SPEC-001 R-7, R-11, R-12, R-15, R-16, NFR-5). 이 문서를 바꾸면 두 모듈을 함께 고친다.

## 형식

- JWT (RFC 7519), JWS Compact Serialization
- 서명 알고리즘: `ES256` (ECDSA P-256 + SHA-256). 다른 알고리즘과 `none`은 거부한다.
- 유효기간: 발급 시각부터 900초(15분)

### 헤더

| 필드 | 값 |
| --- | --- |
| `alg` | `ES256` |
| `typ` | `JWT` |
| `kid` | 서명 키 ID. 공개키 목록(JWKS)의 `kid`와 같다 |

### 클레임

| 클레임 | 타입 | 값 | 검증 |
| --- | --- | --- | --- |
| `sub` | string (UUID) | 사용자 ID | 게이트웨이가 `X-User-Id` 헤더로 전달 |
| `roles` | string 배열 | `USER`, `OPERATOR`, `ADMIN` 중 하나 이상 | 게이트웨이가 쉼표로 이어 `X-User-Roles` 헤더로 전달 |
| `iss` | string | 환경별 발급자. 로컬 `vlm-auth-local`, dev `vlm-auth-dev` | 게이트웨이 설정값과 같아야 함 (R-15) |
| `aud` | string | `vlm-api` | 같아야 함 (R-15) |
| `iat` | number | 발급 시각 (epoch 초) | — |
| `exp` | number | 만료 시각 (epoch 초) = `iat` + 900 | 지났으면 `AUTH_TOKEN_EXPIRED` (R-16). 허용 오차 30초 |
| `jti` | string (UUID) | 토큰 ID | 이번 spec에서는 검증하지 않음 (강제 만료는 범위 밖) |

이메일, 닉네임 같은 개인정보는 클레임에 넣지 않는다. 필요하면 `GET /api/v1/auth/me`로 조회한다.

## 공개키 목록 (JWKS)

- 경로: auth-service `GET /.well-known/jwks.json` (클러스터 내부 전용, 게이트웨이가 외부로 라우팅하지 않음)
- 형식: JWK Set (RFC 7517). 키마다 `kty: EC`, `crv: P-256`, `use: sig`, `alg: ES256`, `kid`를 둔다.
- 개인키는 auth-service만 가진다. 로컬은 환경변수, 운영은 Secrets Manager로 주입한다.

## 키 교체 규칙

교체 중에도 이미 발급된 토큰이 거부되지 않아야 한다(NFR-5).

1. 새 키를 JWKS에 추가한다. 서명은 아직 이전 키로 한다.
2. 10분 이상 지난 뒤 새 키로 서명을 시작한다. 게이트웨이가 새 키를 받아 갈 시간이다.
3. 이전 키로 서명한 마지막 토큰이 만료될 때까지(15분 + 허용 오차) 이전 키를 JWKS에 남긴 뒤 지운다.

게이트웨이는 다음을 지킨다.

- JWKS를 캐시하고 5분 이내 주기로 다시 받는다.
- 캐시에 없는 `kid`의 토큰을 받으면 JWKS를 한 번 즉시 다시 받아 확인한다. 그래도 없으면 `AUTH_TOKEN_INVALID`다.

## 오류 코드 (게이트웨이)

| 상황 | 상태 | `code` |
| --- | --- | --- |
| `Authorization: Bearer` 헤더 없음 | 401 | `AUTH_TOKEN_MISSING` |
| 서명, `alg`, `kid`, `iss`, `aud` 중 하나라도 불일치 | 401 | `AUTH_TOKEN_INVALID` |
| `exp` 지남 | 401 | `AUTH_TOKEN_EXPIRED` |
