#!/bin/sh
# ai-gateway 계정과 DB를 만든다(SPEC-009 호출 로그). PostgreSQL 컨테이너가 데이터 볼륨을 처음 만들 때 한 번만 실행된다.
# 비밀번호는 셸 문자열에 끼워 넣지 않고 psql 변수로 넘겨 따옴표가 섞여도 깨지지 않게 한다.
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
  -v ai_password="$AI_DB_PASSWORD" <<'SQL'
CREATE ROLE ai LOGIN PASSWORD :'ai_password';
CREATE DATABASE ai_db OWNER ai;
SQL
