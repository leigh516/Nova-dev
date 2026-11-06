import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture(scope="session", autouse=True)
def _worktree_write_allowed():
    """worktree 에서 돌려도 테스트가 통과하게 단일 기록자 가드(require_main)를 연다.

    테스트는 임시 저장소에만 쓰므로 단일 기록자(번호 기록은 main 만) 규칙의 대상이 아니다.
    가드 자체를 시험하는 테스트는 스스로 delenv 한다. 세션 범위인 이유: module 범위 픽스처(made 등)가
    함수 범위 픽스처보다 먼저 하위 프로세스를 띄우고, 하위 프로세스는 이 환경을 물려받아야 하기 때문이다.
    """
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("NOVA_ALLOW_WORKTREE_WRITE", "1")
        yield


@pytest.fixture(scope="session", autouse=True)
def _subprocess_stdin_devnull():
    """테스트가 띄우는 하위 프로세스가 작업자(xdist)의 표준 입력 파이프를 상속하지 않게 한다.

    stdin 을 따로 주지 않은 호출에만 DEVNULL 을 채운다(명시한 호출은 그대로). scripts 쪽 코드는 건드리지 않는다.
    """
    original = subprocess.Popen.__init__

    def init(self, *args, **kwargs):
        if kwargs.get("stdin") is None and kwargs.get("input") is None:
            kwargs["stdin"] = subprocess.DEVNULL
        original(self, *args, **kwargs)

    subprocess.Popen.__init__ = init
    try:
        yield
    finally:
        subprocess.Popen.__init__ = original
