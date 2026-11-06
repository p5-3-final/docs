# 로컬 compose

로컬 개발 머신에서 서비스를 한 번에 띄우는 구성이다. 지금은 PostgreSQL, Redis, Kafka, SeaweedFS(S3 대체, ADR-0006), auth-service, media-service, api-gateway, frontend, normalize(SPEC-007), frame-encoder(SPEC-019), event-analyzer(SPEC-020), ai-gateway(SPEC-009)가 들어 있고, 서비스 구현이 시작되면 추가한다.

| 컨테이너 | 호스트 포트 | 메모리 상한 |
| --- | --- | --- |
| frontend (nginx) | 3000 | 64M |
| api-gateway | 8080 | 512M |
| auth-service | 8081 | 768M |
| media-service | 8082 | 768M |
| normalize | — (health 8000, 내부) | 768M |
| frame-encoder | — (health 8000, 내부) | 1G |
| event-analyzer | — (health 8000, 내부) | 256M |
| ai-gateway (내부 전용 API) | 8000 | 768M |
| postgres (auth_db, media_db, ai_db) | 5432 | 512M |
| redis | 6379 | 128M |
| kafka (KRaft 단일 노드) | 9092 | 512M |
| seaweedfs (S3 API, 버킷 `vlm-media`) | 8333 | 384M |

`seaweedfs-init`은 버킷(영상 `vlm-media`, 모델 가중치 `vlm-models`)을 만들고 끝나는 일회성 컨테이너다. SeaweedFS 접근 키는 `seaweedfs/s3.json`의 로컬 전용 샘플값이고 compose의 media-service·normalize·frame-encoder·ai-gateway 설정과 같다. `s3.json`을 바꾸면 SeaweedFS를 다시 시작해야 반영된다.

`kafka-init`은 normalize·frame-encoder·event-analyzer·ai-gateway가 쓰는 토픽(재시도·DLQ, 처리 단계 측정 `stage.timing` 포함)을 미리 만들고 끝나는 일회성 컨테이너다. 컨슈머는 없는 토픽을 구독하면 메타데이터를 다시 읽을 때까지(기본 5분) 알아채지 못한다.

## 준비

- Docker Desktop 또는 OrbStack
- `./scripts/clone-repos.sh`로 `repos/backend`, `repos/frontend`, `repos/ai`를 클론해 둔다. 이미지는 각 레포의 `Dockerfile`로 빌드한다.

## 실행

```bash
# 예시 파일에 로컬 전용 샘플값(비밀번호, 서명 키, 초기 관리자 admin@example.com)이 들어 있어 복사만 하면 뜬다.
# 서명 키를 새로 만들려면 (cd repos/backend && ./gradlew -q :services:auth-service:generateSigningKey)
cp local/.env.example local/.env

docker compose -f local/docker-compose.yml up -d --build
docker compose -f local/docker-compose.yml ps
```

브라우저에서 <http://localhost:3000>을 열면 frontend 화면이 나온다. 로그인 칸에 샘플 관리자(`admin@example.com` / `admin1234`)가 미리 채워져 있다. `local/.env`의 `AUTH_ADMIN_*`를 바꿨다면 `repos/frontend/.env.compose`도 같이 바꾼다. Safari는 `http://localhost`에서 `Secure` 쿠키를 저장하지 않을 수 있어 Chrome 계열을 쓴다.

게이트웨이를 거쳐 API로 가입 → 로그인 → 내 정보를 확인한다.

```bash
curl -s -X POST localhost:8080/api/v1/auth/signup -H 'Content-Type: application/json' \
  -d '{"email":"user@example.com","password":"secret123","nickname":"테스터"}'
TOKEN=$(curl -s -X POST localhost:8080/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"user@example.com","password":"secret123"}' | jq -r .accessToken)
curl -s localhost:8080/api/v1/auth/me -H "Authorization: Bearer $TOKEN"
```

### 영상 업로드 (SPEC-003)

위에서 받은 `TOKEN`으로 업로드 자리를 받고, 응답의 주소로 저장소(localhost:8333)에 직접 올린 뒤 완료를 요청한다. 100MB 이하는 POST 폼(`SINGLE`), 넘으면 조각별 PUT(`MULTIPART`)이다.

```bash
head -c 1000000 /dev/urandom > /tmp/small.mp4
C=$(curl -s -X POST localhost:8080/api/v1/media/videos -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"fileName":"small.mp4","sizeBytes":1000000,"contentType":"video/mp4"}')
ID=$(jq -r .video.id <<<"$C")
# 응답의 fields를 모두 폼 필드로 넣고 마지막에 file을 넣는다.
FORM=(); for k in $(jq -r '.upload.fields|keys[]' <<<"$C"); do FORM+=(-F "$k=$(jq -r --arg k "$k" '.upload.fields[$k]' <<<"$C")"); done
curl -s -o /dev/null -w '%{http_code}\n' "${FORM[@]}" -F file=@/tmp/small.mp4 "$(jq -r .upload.url <<<"$C")"   # 204
curl -s -X POST localhost:8080/api/v1/media/videos/$ID/complete -H "Authorization: Bearer $TOKEN" | jq .status   # "UPLOADED"
```

멀티파트는 `upload.parts[].url`마다 `partSizeBytes`만큼 잘라 PUT하고, 응답의 `ETag` 헤더를 모아 `{"parts":[{"partNumber":1,"eTag":"..."}]}`로 완료를 요청한다. 발행된 이벤트는 Kafka 콘솔 도구로 본다.

```bash
docker compose -f local/docker-compose.yml exec kafka /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 --topic video.uploaded --from-beginning
```

브라우저(frontend)에서 저장소로 바로 올리는 CORS 설정은 frontend 업로드 화면 spec에서 다룬다.

### ai-gateway 분석 호출 (SPEC-009)

`ai-gateway-migrate`가 호출 로그 테이블을 만들고 끝나면 ai-gateway가 뜬다. 기본 프로필은 모델 없이 흐름만 보는 mock(`/app/profiles/local-mock.toml`)이다. ai-gateway는 내부 전용이라 api-gateway를 거치지 않고 8000으로 직접 부른다.

이미지는 허용 패턴(`sources/<sourceId>/.../blurred/*.jpg` 등)에 맞는 블러 사본 경로만 받는다. 아래는 영상 폴더에 이미지를 하나 넣었다고 가정한 예시다.

```bash
curl -s -X POST localhost:8000/v1/analyze -H 'Content-Type: application/json' -H 'X-Caller: event-analyzer' \
  -d "{\"taskType\":\"event_judge\",\"sourceId\":\"$ID\",
       \"images\":[{\"storageKey\":\"sources/$ID/chunks/0/candidates/c1/blurred/000.jpg\",\"ptsSec\":1.0}],
       \"variables\":{\"eventType\":\"fall\",\"startSec\":0.5,\"endSec\":3.0}}" | jq .output
docker compose -f local/docker-compose.yml exec postgres psql -U postgres -d ai_db \
  -c 'SELECT caller, model_id, status, latency_ms FROM ai.ai_call_log ORDER BY created_at DESC LIMIT 5'
```

- 로컬 Ollama(Qwen3-VL)로 실제 모델을 부르려면 호스트에서 Ollama를 띄운다. Mac의 Docker는 GPU를 쓰지 못해 컨테이너보다 호스트가 훨씬 빠르다. ai-gateway는 `host.docker.internal`로 호스트의 Ollama에 붙는다. Ollama는 DNS rebinding 방지로 그 밖의 호스트 이름 요청을 403으로 거절한다.

  ```bash
  ollama serve &                 # 이미 떠 있으면 생략
  ollama pull qwen3-vl:4b-instruct   # 프로필 local.toml의 모델. 생각 단계가 없는 판이라 출력 상한 안에 답한다
  ollama pull bge-m3                 # local.toml의 텍스트 임베딩(아래 "벡터 생성")
  AI_GATEWAY_PROFILE_PATH=/app/profiles/local.toml docker compose -f local/docker-compose.yml up -d ai-gateway
  ```

  계속 쓰려면 `local/.env`에 `AI_GATEWAY_PROFILE_PATH=/app/profiles/local.toml`을 넣는다. 첫 호출은 모델을 메모리에 올리느라 더 오래 걸린다.
- 기존 DB 볼륨에 ai_db를 더하려면 아래 "자주 쓰는 명령"의 postgres/init 안내처럼 `30-ai-db.sh`만 실행한다.

### ai-gateway Registry 묶음 (SPEC-009 R-26)

기본은 이미지에 넣은 Prompt Registry와 프로필을 쓴다. 운영처럼 모델 버킷의 묶음으로 띄워 보려면 아래를 한다.

```bash
local/scripts/upload-registry.sh   # 이미지의 Registry·프로필로 묶음을 만들어 vlm-models에 올리고 설정 세 줄을 출력한다
```

- 출력한 `AI_GATEWAY_REGISTRY_BUNDLE`·`AI_GATEWAY_REGISTRY_BUNDLE_SHA256`·`AI_GATEWAY_PROFILE_PATH`(묶음 안 상대 경로)를 `local/.env`에 넣고 ai-gateway를 다시 띄운다. 지우면 이미지의 것으로 돌아간다.
- 프롬프트나 프로필을 바꾸면 이미지를 다시 빌드하고 스크립트를 다시 실행한다. 내용이 바뀌면 해시와 경로가 함께 바뀐다.
- 새 taskType은 ai 레포 `services/ai-gateway/registry/prompts/<taskType>/`(프롬프트, 입력·출력 스키마와 예시, `fallback.json`)와 프로필의 `[tasks.<taskType>]`만 더한다(R-24).

### frame-encoder 구간·크롭 벡터 (SPEC-019)

frame-encoder는 `segment.ready`를 받아 실행 폴더의 블러 이미지를 벡터로 바꾸고 `vectors.json`을 저장한 뒤 `segment.embedded`를 발행한다. 프로필에 프로토타입이 있으면 임계값을 넘은 구간을 `event.candidate.vector`로 발행한다. `segment.ready`를 발행하는 chunk-processor는 아직 compose에 없어, 지금은 메시지를 직접 넣어 확인한다.

- 기본 프로필은 mock(`/app/profiles/local-mock.toml`)이다. 벡터에 의미가 없고 모든 구간이 후보가 된다(흐름 확인용).
- 실제 인코더는 위 ai-gateway와 같은 가중치를 쓴다. `local/scripts/upload-models.sh`를 한 번 실행한 뒤 프로필을 바꾼다. ai-gateway도 `local.toml`로 맞춰야 질의 벡터와 같은 공간이 된다.

```bash
FRAME_ENCODER_PROFILE_PATH=/app/profiles/local.toml docker compose -f local/docker-compose.yml up -d frame-encoder
```

- 받은 가중치는 `frame-encoder-models` 볼륨에 남는다. manifest·가중치 해시가 프로필과 다르면 뜨지 않는다.
- `local.toml`의 프로토타입 문장·임계값은 흐름 확인용 예시다. 후보 품질을 로컬 결과로 판단하지 않는다.
- 실행 폴더 `blurred/` 밖 경로를 가리키거나 이미지가 없는 메시지는 `frame-encoder.dlq`로 간다.

### event-analyzer 벡터 후보 판정 (SPEC-020)

event-analyzer는 `event.candidate.vector`를 받아 후보마다 ai-gateway `event_judge`로 판정하고, severity `high`이거나 판단 불가면 `event_judge_escalate`로 다시 판정한 뒤 후보마다 `event.analyzed`를 발행한다. 판정 모델은 ai-gateway 프로필이 정한다.

```bash
docker compose -f local/docker-compose.yml up -d frame-encoder event-analyzer
```

- 기본 mock 프로필은 출력 스키마의 첫 예시(severity `high`)를 돌려주므로 모든 후보가 재판정되어 `vector+vlm+escalate`로 기록된다.
- 실제 판정은 ai-gateway를 `AI_GATEWAY_PROFILE_PATH=/app/profiles/local.toml`(호스트 Ollama)로 띄운다. 로컬은 1차와 재판정이 같은 모델이다.
- ai-gateway가 응답하지 않으면 재시도한 뒤 그 후보를 `unknown`과 실패 코드로 발행한다. 호출자 거절(403) 같은 설정 오류나 계약에 맞지 않는 메시지는 `event-analyzer.dlq`로 간다.

### ai-gateway 벡터 생성 (SPEC-011)

`/v1/embed`는 문장·검색용 이미지·텍스트를 벡터로 바꾼다. mock 프로필은 의미 없는 결정적 벡터를 돌려준다. 실제 인코더(MobileCLIP2-S0)와 텍스트 임베딩(Ollama `bge-m3`)을 쓰려면 아래를 한 번 한다.

```bash
local/scripts/upload-models.sh   # Hugging Face에서 가중치(약 300MB)를 받아 sha256 확인 후 manifest와 함께 vlm-models 버킷에 올린다
ollama pull bge-m3               # 텍스트 임베딩(한국어 포함, 1024차원)
AI_GATEWAY_PROFILE_PATH=/app/profiles/local.toml docker compose -f local/docker-compose.yml up -d ai-gateway
```

- 가중치는 이미지에 넣지 않는다. 버킷의 `models/mobileclip2-s0/dfndr2b/`에 가중치와 `manifest.json`(파일 sha256·차원·출처)을 둔다. ai-gateway가 기동할 때 프로필이 가리키는 manifest를 받아 프로필의 sha256과 맞춰 보고, manifest에 적힌 가중치를 받아 sha256을 확인한다. 받은 파일은 `ai-gateway-models` 볼륨에 남겨 재시작 때 다시 받지 않는다. 해시가 다르면 뜨지 않는다.
- 가중치(Apple AMLR)는 비상용 시연·학습 목적으로만 쓴다(docs overview "모델과 플랫폼 교체").
- 검색용 이미지는 `queries/<질의 ID>/` 아래 경로만 받는다. 영상 폴더의 경로는 거부한다.

```bash
curl -s -X POST localhost:8000/v1/embed -H 'Content-Type: application/json' -H 'X-Caller: search-service' \
  -d '{"taskType":"embed_visual_text","texts":["a forklift"]}' | jq '{modelId, dimension}'
curl -s -X POST localhost:8000/v1/embed -H 'Content-Type: application/json' -H 'X-Caller: embedding-worker' \
  -d '{"taskType":"embed_text","texts":["작업자가 지게차 옆에 넘어졌다"]}' | jq '{modelId, dimension}'
```

- Ollama를 멈춰도 `embed_visual_text`·`embed_image`는 동작한다. `embed_text`는 503 `AI_PROVIDER_UNAVAILABLE`이다.

## 자주 쓰는 명령

```bash
docker compose -f local/docker-compose.yml logs -f auth-service     # 로그
docker compose -f local/docker-compose.yml up -d --build api-gateway # 코드를 바꾼 서비스만 다시 빌드
docker compose -f local/docker-compose.yml down                     # 중지
docker compose -f local/docker-compose.yml down -v                  # 중지하고 DB 데이터까지 삭제
```

- `postgres/init`의 스크립트는 DB 볼륨을 처음 만들 때만 실행된다. 비밀번호를 바꿨거나 서비스 DB를 추가했다면 `down -v`로 볼륨을 지우고 다시 띄운다.
  - 데이터를 남긴 채 새 서비스 DB만 추가하려면, `local/.env`에 새 비밀번호 변수(예: `MEDIA_DB_PASSWORD`)를 넣고 postgres를 다시 띄운 뒤 그 스크립트만 실행한다.

    ```bash
    docker compose -f local/docker-compose.yml up -d postgres
    docker compose -f local/docker-compose.yml exec -e POSTGRES_USER=postgres postgres \
      sh /docker-entrypoint-initdb.d/20-media-db.sh   # ai_db는 30-ai-db.sh
    ```
