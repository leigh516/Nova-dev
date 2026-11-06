-- 생성 파일 — scripts/gen_k3s.py (services.json). 직접 고치지 않는다.
-- 서비스별 스키마 + 전용 계정(자기 스키마에만 권한 — 교차 조인 · 교차 쓰기 불가). 비밀번호는 개발용 고정값.
-- 테이블은 각 서비스가 기동 시 마이그레이션(Alembic 플랫폼 + 서비스 분기, ADR-011)으로 만든다. migrations 폴더가 없는 서비스만 create_all.
CREATE DATABASE IF NOT EXISTS sample CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'sample'@'%' IDENTIFIED BY 'dev-sample-pw';
GRANT ALL PRIVILEGES ON sample.* TO 'sample'@'%';
FLUSH PRIVILEGES;
