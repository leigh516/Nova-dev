"""__SERVICE__ 마이그레이션 환경 — 설정은 nova_common.migrate.run_env 한 곳에 있다(ADR-011).

실행: 서비스 기동(Service.init_db)이 플랫폼 + 이 서비스 분기를 heads 까지 올린다. 새 리비전은 `python nova.py migrate __SERVICE__ new "<설명>"`.
"""
from nova_common.migrate import run_env

run_env()
