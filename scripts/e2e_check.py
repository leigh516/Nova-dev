#!/usr/bin/env python3
"""실행 중인 스택(게이트웨이 URL)을 대상으로 샘플 흐름을 검증한다 — e2e_kafka.sh 가 호출.

  uv run python scripts/e2e_check.py http://127.0.0.1:8080/v1
검증: 개발 로그인 → 항목 생성 → Kafka 경유 이벤트 소비(활동 기록 생김) → 보관 이벤트 → 권한 403.
새 서비스를 만들면 그 서비스의 핵심 흐름을 여기 추가한다.
"""
import sys
import time

import httpx

API = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080/v1"
c = httpx.Client(base_url=API, timeout=10)


def login(email: str) -> dict:
    r = c.post("/auth/login", json={"email": email, "password": "nova1234"})
    r.raise_for_status()
    return {"authorization": "Bearer " + r.json()["token"]}


def wait_activity(h: dict, item_id: str, kinds: list[str], timeout: float = 20.0) -> float:
    t0 = time.time()
    got: list[str] = []
    while time.time() - t0 < timeout:
        got = [a["kind"] for a in c.get(f"/sample/items/{item_id}", headers=h).json()["activity"]]
        if got == kinds:
            return time.time() - t0
        time.sleep(0.2)
    raise AssertionError(f"활동 기록 {got} (기대 {kinds})")


def main() -> int:
    user = login("user@nova.dev")
    item = c.post("/sample/items", json={"name": "e2e"}, headers=user)
    assert item.status_code == 201, item.text
    iid = item.json()["id"]
    dt = wait_activity(user, iid, ["created"])
    print(f"✓ 생성 → Kafka → 소비 {dt:.2f}s")
    assert c.post(f"/sample/items/{iid}/archive", headers=user).json()["status"] == "archived"
    dt = wait_activity(user, iid, ["created", "archived"])
    print(f"✓ 보관 이벤트 소비 {dt:.2f}s")
    r = c.delete(f"/sample/items/{iid}", headers=user)
    assert r.status_code == 403 and r.json()["error"]["perm"] == "sample.delete", r.text
    print("✓ 권한 검사(user 는 sample.delete 없음) 403")
    print("E2E 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
