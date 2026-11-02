---
id: SPEC-001
title: 회원가입·로그인과 인증된 요청
status: Implementing
owner: <이름>
repos: [backend]
created: 2026-11-02
updated: 2026-11-02
related: []
---

# SPEC-001 회원가입·로그인과 인증된 요청

> 이 문서에는 **무엇을, 왜**만 쓴다. 클래스, 테이블, 라이브러리 같은 구현 방법은 각 레포의 plan.md에 쓴다.

## 1. 배경과 목적
영상 업로드, 분석 결과 조회, 검색은 모두 "누구의 영상인가"를 기준으로 권한을 판단한다. 그래서 사용자가 가입하고 로그인해야 하고, 모든 외부 요청이 한 곳(api-gateway)에서 인증된 뒤 각 서비스로 전달되어야 한다. 각 서비스는 게이트웨이가 넘겨준 사용자 정보만 믿고 인가(소유자, 역할)를 판단한다.

이 spec은 이후 모든 기능 spec의 전제가 된다.

## 2. 범위
### 포함
- 이메일 회원가입, 로그인, 내 정보 조회
- 짧은 수명의 접근 토큰과 회전하는 재발급 토큰, 로그아웃
- 게이트웨이의 경로별 전달, 토큰 검증, 사용자 정보 전달, 오류 응답
- 실시간 알림 연결용 1회용 티켓
- 로그인 남용 방지 (계정 잠금, 요청 수 제한)
- 초기 관리자 계정 1개 생성

### 제외
- 소셜 로그인, SSO, 외부 인증 제공자
- 이메일 인증, 비밀번호 찾기·변경, 회원 탈퇴
- 역할 변경 기능 (운영자·관리자 지정)
- 발급된 접근 토큰의 즉시 강제 만료
- frontend 화면 (별도 spec)

## 3. 사용자 시나리오

### US-1 회원가입 (P1)
처음 방문한 사용자로서 이메일로 가입하고 싶다. 왜냐하면 내 영상을 올리고 분석 결과를 나만 보고 싶기 때문이다.

**인수 조건**
- Given 가입되지 않은 이메일, When 올바른 형식의 이메일·비밀번호·닉네임으로 가입하면, Then 계정이 USER 역할로 만들어진다.
- Given 이미 가입된 이메일, When 같은 이메일로 가입하면, Then 중복이라는 오류를 받는다.

### US-2 로그인과 내 정보 조회 (P1)
가입한 사용자로서 로그인하고 내 정보를 확인하고 싶다. 왜냐하면 이후 모든 기능을 내 계정으로 쓰기 때문이다.

**인수 조건**
- Given 가입된 계정, When 올바른 이메일과 비밀번호로 로그인하면, Then 접근 토큰과 재발급 토큰을 받는다.
- Given 로그인한 사용자, When 접근 토큰으로 내 정보를 요청하면, Then 이메일, 닉네임, 역할을 받는다.
- Given 틀린 비밀번호, When 로그인하면, Then 이메일과 비밀번호 중 무엇이 틀렸는지 알려 주지 않는 오류를 받는다.

### US-3 인증된 요청 전달 (P1)
서비스 개발자로서 모든 외부 요청이 게이트웨이에서 인증된 뒤 전달되기를 원한다. 왜냐하면 각 서비스가 토큰 검증을 반복하지 않고 사용자 정보만 보고 인가할 수 있기 때문이다.

**인수 조건**
- Given 유효한 접근 토큰, When 보호된 경로를 요청하면, Then 해당 서비스가 검증된 사용자 ID와 역할을 받는다.
- Given 토큰이 없거나 위조되었거나 만료됨, When 보호된 경로를 요청하면, Then 401을 받고 요청은 서비스로 전달되지 않는다.
- Given 클라이언트가 사용자 ID 헤더를 직접 넣음, When 요청하면, Then 그 값은 서비스에 전달되지 않는다.

### US-4 로그인 유지와 로그아웃 (P2)
로그인한 사용자로서 접근 토큰이 만료돼도 다시 로그인하지 않고 계속 쓰고, 원할 때 로그아웃하고 싶다.

**인수 조건**
- Given 유효한 재발급 토큰, When 재발급을 요청하면, Then 새 접근 토큰과 새 재발급 토큰을 받고 이전 재발급 토큰은 더 쓸 수 없다.
- Given 이미 사용한 재발급 토큰, When 다시 재발급을 요청하면, Then 거절되고 그 계정의 해당 로그인 계열 토큰이 모두 폐기된다.
- Given 로그인한 사용자, When 로그아웃하면, Then 재발급 토큰이 폐기된다.

### US-5 실시간 알림 연결 인증 (P2)
로그인한 사용자로서 분석 진행 알림을 실시간으로 받고 싶다. 브라우저의 알림 연결은 인증 헤더를 붙일 수 없어서 별도 티켓으로 인증한다.

**인수 조건**
- Given 로그인한 사용자, When 티켓을 요청하면, Then 30초 동안 한 번만 쓸 수 있는 티켓을 받는다.
- Given 사용했거나 만료된 티켓, When 알림 연결을 시도하면, Then 401을 받는다.

### US-6 로그인 남용 방지 (P2)
서비스 운영자로서 비밀번호 대입 공격을 막고 싶다.

**인수 조건**
- Given 같은 계정에 연속 5회 로그인 실패, When 다시 로그인하면, Then 15분 동안 거절된다.
- Given 같은 IP에서 1분에 10회를 넘는 로그인·가입 요청, When 요청하면, Then 429를 받는다.

## 4. 요구사항

### 기능 요구사항 (EARS)
| ID | 요구사항 | 시나리오 |
| --- | --- | --- |
| R-1 | WHEN 사용자가 가입되지 않은 이메일, 정책에 맞는 비밀번호, 닉네임으로 가입을 요청하면, THE auth-service SHALL USER 역할의 계정을 만들고 201을 반환한다. | US-1 |
| R-2 | IF 가입 요청의 이메일이 이미 가입되어 있으면, THEN THE auth-service SHALL 409와 오류 코드 `AUTH_EMAIL_DUPLICATED`를 반환한다. | US-1 |
| R-3 | IF 가입 요청의 이메일 형식이 올바르지 않으면, THEN THE auth-service SHALL 400과 오류 코드 `AUTH_INVALID_REQUEST`를 반환한다. | US-1 |
| R-4 | IF 가입 요청의 비밀번호가 8~64자가 아니거나 영문과 숫자를 모두 포함하지 않으면, THEN THE auth-service SHALL 400과 오류 코드 `AUTH_PASSWORD_POLICY`를 반환한다. | US-1 |
| R-5 | IF 가입 요청의 닉네임이 2~20자가 아니거나 한글, 영문, 숫자 외의 문자를 포함하면, THEN THE auth-service SHALL 400과 오류 코드 `AUTH_INVALID_REQUEST`를 반환한다. | US-1 |
| R-6 | THE auth-service SHALL 비밀번호를 원문으로 복원할 수 없는 형태로만 저장한다. | US-1 |
| R-7 | WHEN 사용자가 올바른 이메일과 비밀번호로 로그인하면, THE auth-service SHALL 유효기간 15분의 접근 토큰을 응답 본문으로, 유효기간 14일의 재발급 토큰을 HttpOnly·Secure·SameSite 쿠키로 반환한다. | US-2 |
| R-8 | IF 로그인 요청의 이메일이 없거나 비밀번호가 틀리면, THEN THE auth-service SHALL 두 경우를 구분하지 않고 401과 오류 코드 `AUTH_INVALID_CREDENTIALS`를 반환한다. | US-2 |
| R-9 | WHEN 로그인 시도가 끝나면, THE auth-service SHALL 시각, 대상 계정, 성공 여부, 요청 IP를 로그인 기록으로 남긴다. | US-2, US-6 |
| R-10 | WHEN 인증된 사용자가 내 정보를 요청하면, THE auth-service SHALL 사용자 ID, 이메일, 닉네임, 역할을 반환한다. | US-2 |
| R-11 | THE auth-service SHALL 접근 토큰 서명을 검증할 공개키 목록을 클러스터 내부 경로로 제공하고, 키 교체 기간에는 새 키와 이전 키를 함께 제공한다. | US-3 |
| R-12 | WHEN 유효한 접근 토큰이 담긴 요청이 보호된 경로로 들어오면, THE api-gateway SHALL 경로에 해당하는 서비스로 요청을 전달하고 검증된 사용자 ID와 역할을 헤더로 붙인다. | US-3 |
| R-13 | WHEN 가입, 로그인, 토큰 재발급, health 경로로 요청이 들어오면, THE api-gateway SHALL 토큰 없이 해당 서비스로 전달한다. | US-1, US-2, US-4 |
| R-14 | IF 보호된 경로 요청에 접근 토큰이 없으면, THEN THE api-gateway SHALL 401과 오류 코드 `AUTH_TOKEN_MISSING`을 반환한다. | US-3 |
| R-15 | IF 접근 토큰의 서명, 발급자, 대상 중 하나라도 맞지 않으면, THEN THE api-gateway SHALL 401과 오류 코드 `AUTH_TOKEN_INVALID`를 반환한다. | US-3 |
| R-16 | IF 접근 토큰이 만료되었으면, THEN THE api-gateway SHALL 401과 오류 코드 `AUTH_TOKEN_EXPIRED`를 반환한다. | US-3 |
| R-17 | WHEN 클라이언트 요청에 게이트웨이가 붙이는 사용자 정보 헤더와 같은 이름의 헤더가 있으면, THE api-gateway SHALL 그 헤더를 제거한 뒤 처리한다. | US-3 |
| R-18 | IF 요청 경로가 어느 서비스에도 해당하지 않으면, THEN THE api-gateway SHALL 404와 오류 코드 `GATEWAY_ROUTE_NOT_FOUND`를 반환한다. | US-3 |
| R-19 | IF 전달한 서비스가 제한 시간 안에 응답하지 않으면, THEN THE api-gateway SHALL 504와 오류 코드 `GATEWAY_TIMEOUT`을 반환한다. | US-3 |
| R-20 | IF 전달할 서비스에 연결할 수 없으면, THEN THE api-gateway SHALL 503과 오류 코드 `GATEWAY_UNAVAILABLE`을 반환한다. | US-3 |
| R-21 | IF 브라우저 교차 출처 요청의 출처가 허용 목록(frontend 주소)에 없으면, THEN THE api-gateway SHALL 교차 출처 허용 헤더 없이 응답한다. | US-3 |
| R-22 | WHEN 사용자가 유효한 재발급 토큰으로 재발급을 요청하면, THE auth-service SHALL 새 접근 토큰과 새 재발급 토큰을 발급하고 제출된 재발급 토큰을 무효로 만든다. | US-4 |
| R-23 | IF 이미 사용된 재발급 토큰이 다시 제출되면, THEN THE auth-service SHALL 그 토큰과 같은 로그인 계열의 재발급 토큰을 모두 폐기하고 401과 오류 코드 `AUTH_REFRESH_REUSED`를 반환한다. | US-4 |
| R-24 | IF 재발급 토큰이 없거나 만료되었거나 폐기되었으면, THEN THE auth-service SHALL 401과 오류 코드 `AUTH_REFRESH_INVALID`를 반환한다. | US-4 |
| R-25 | WHEN 인증된 사용자가 로그아웃을 요청하면, THE auth-service SHALL 해당 재발급 토큰을 폐기하고 재발급 토큰 쿠키를 지우며 204를 반환한다. | US-4 |
| R-26 | WHEN 인증된 사용자가 알림 연결 티켓을 요청하면, THE auth-service SHALL 30초 동안 한 번만 쓸 수 있는 티켓을 발급한다. | US-5 |
| R-27 | WHEN 유효한 티켓으로 알림 연결 요청이 들어오면, THE api-gateway SHALL 티켓을 사용 처리하고 티켓 주인의 사용자 ID와 역할을 헤더로 붙여 notification-service로 전달한다. | US-5 |
| R-28 | IF 알림 연결 요청의 티켓이 없거나 만료되었거나 이미 사용되었으면, THEN THE api-gateway SHALL 401과 오류 코드 `AUTH_TICKET_INVALID`를 반환한다. | US-5 |
| R-29 | IF 같은 계정의 로그인이 연속 5회 실패하면, THEN THE auth-service SHALL 그 뒤 15분 동안 그 계정의 로그인을 423과 오류 코드 `AUTH_ACCOUNT_LOCKED`로 거절한다. | US-6 |
| R-30 | IF 같은 IP에서 로그인·가입 요청이 1분에 10회를 넘으면, THEN THE api-gateway SHALL 초과 요청에 429와 오류 코드 `GATEWAY_RATE_LIMITED`를 반환한다. | US-6 |
| R-31 | WHEN auth-service가 처음 시작될 때 관리자 계정이 하나도 없으면, THE auth-service SHALL 배포 환경의 비밀값으로 지정한 이메일과 비밀번호로 ADMIN 계정 하나를 만든다. | — (운영 준비) |

### 비기능 요구사항
| ID | 요구사항 |
| --- | --- |
| NFR-1 | THE api-gateway SHALL 토큰 검증과 전달로 더하는 지연을 p95 50ms 이하로 유지한다(하위 서비스 처리 시간 제외). |
| NFR-2 | THE auth-service SHALL 재발급 토큰과 알림 티켓을 원문으로 복원할 수 없는 형태로만 저장한다. |
| NFR-3 | THE auth-service, api-gateway SHALL 비밀번호, 토큰, 티켓 원문을 로그에 남기지 않는다. |
| NFR-4 | THE api-gateway SHALL 모든 오류 응답을 공통 오류 형식(ProblemDetail)으로 반환하고 추적 ID를 포함한다. |
| NFR-5 | WHEN 서명 키를 교체하면, THE api-gateway SHALL 교체 전에 발급된 유효한 접근 토큰을 만료 시각까지 계속 받아들인다. |

## 5. 영향 범위
| 레포 / 서비스 | 변경 개요 | 담당 요구사항 |
| --- | --- | --- |
| backend / auth-service | 가입, 로그인, 내 정보, 토큰 발급·재발급·폐기, 공개키 제공, 알림 티켓, 계정 잠금, 초기 관리자 | R-1~R-11, R-22~R-26, R-29, R-31, NFR-2, NFR-3 |
| backend / api-gateway | 경로별 전달, 토큰 검증, 사용자 헤더 전달·위조 헤더 제거, 오류 응답, CORS, 알림 티켓 검증, 요청 수 제한 | R-12~R-21, R-27, R-28, R-30, NFR-1, NFR-3~NFR-5 |
| frontend | 이 spec에서는 변경 없음. 계약을 기준으로 이후 화면 spec에서 사용 | — |

## 6. 계약 변경
| 계약 파일 | 변경 | 하위호환 |
| --- | --- | --- |
| `docs/contracts/openapi/auth-service.yaml` | 신규: `/api/v1/auth` 아래 가입, 로그인, 재발급, 로그아웃, 내 정보, 알림 티켓. 내부 공개키 목록 경로 | 해당 없음 (신규) |
| `docs/contracts/openapi/_common.yaml` | 게이트웨이가 붙이는 사용자 정보 헤더 정의, 게이트웨이 오류 코드 추가 | 예 (추가) |
| `docs/contracts/auth/access-token.md` | 신규: 접근 토큰 클레임(`sub`, `roles`, `iss`, `aud`, `exp`, `jti`), 서명 방식, 공개키 목록 경로, 키 교체 규칙 | 해당 없음 (신규) |

## 7. 성공 지표
- P1 시연: 가입 → 로그인 → 게이트웨이를 거친 내 정보 조회가 로컬 compose에서 한 번에 동작한다.
- R-1~R-31 각각에 대응하는 자동화 테스트가 통과한다.
- 위조·만료 토큰, 위조 사용자 헤더로 보호된 서비스에 도달하는 경로가 없다(R-14~R-17 테스트).

## 8. 미결 사항
- 해당 없음
