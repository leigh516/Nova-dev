# 얇은 별칭 — 실제 동작은 nova.py (Windows 에 make 가 없어도 python nova.py <명령> 으로 같다)
PY ?= python
.PHONY: install test lint gen run tokens web web-build kmp-test e2e-kafka doctor
install test lint gen run tokens web web-build kmp-test e2e-kafka doctor:
	$(PY) nova.py $@
new-service:
	$(PY) nova.py new-service $(ARGS)
