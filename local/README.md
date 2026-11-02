# 로컬 compose

로컬 개발 머신에서 서비스를 한 번에 띄우는 구성이다. 지금은 PostgreSQL, Redis, auth-service, api-gateway가 들어 있고, 서비스 구현이 시작되면 추가한다.

| 컨테이너 | 호스트 포트 | 메모리 상한 |
| --- | --- | --- |
| api-gateway | 8080 | 512M |
| auth-service | 8081 | 768M |
| postgres (auth_db) | 5432 | 512M |
| redis | 6379 | 128M |

## 준비

- Docker Desktop 또는 OrbStack
- `./scripts/clone-repos.sh`로 `repos/backend`를 클론해 둔다. 이미지는 `repos/backend/Dockerfile`로 빌드한다.

## 실행

```bash
# 예시 파일에 로컬 전용 샘플값(비밀번호, 서명 키, 초기 관리자 admin@example.com)이 들어 있어 복사만 하면 뜬다.
# 서명 키를 새로 만들려면 (cd repos/backend && ./gradlew -q :services:auth-service:generateSigningKey)
cp local/.env.example local/.env

docker compose -f local/docker-compose.yml up -d --build
docker compose -f local/docker-compose.yml ps
```

게이트웨이를 거쳐 가입 → 로그인 → 내 정보를 확인한다.

```bash
curl -s -X POST localhost:8080/api/v1/auth/signup -H 'Content-Type: application/json' \
  -d '{"email":"user@example.com","password":"secret123","nickname":"테스터"}'
TOKEN=$(curl -s -X POST localhost:8080/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"user@example.com","password":"secret123"}' | jq -r .accessToken)
curl -s localhost:8080/api/v1/auth/me -H "Authorization: Bearer $TOKEN"
```

## 자주 쓰는 명령

```bash
docker compose -f local/docker-compose.yml logs -f auth-service     # 로그
docker compose -f local/docker-compose.yml up -d --build api-gateway # 코드를 바꾼 서비스만 다시 빌드
docker compose -f local/docker-compose.yml down                     # 중지
docker compose -f local/docker-compose.yml down -v                  # 중지하고 DB 데이터까지 삭제
```

- `postgres/init`의 스크립트는 DB 볼륨을 처음 만들 때만 실행된다. 비밀번호를 바꿨거나 서비스 DB를 추가했다면 `down -v`로 볼륨을 지우고 다시 띄운다.
