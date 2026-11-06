-- 생성 파일 — scripts/gen_k3s.py (services.json). 직접 고치지 않는다.
-- 운영: 스키마만 만든다(ConfigMap 에 비밀번호 금지). 서비스 계정 · 권한은 db-provision Job 이 만든다(db-provision.sh — 비밀번호는 시크릿 nova-db-provision)
CREATE DATABASE IF NOT EXISTS sample CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
