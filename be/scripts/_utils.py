"""be/scripts 공용 부트스트랩 — sys.path 설정 후 import해야 하는 공통 초기화."""
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_env() -> None:
    env_path = os.path.join(PROJECT_ROOT, ".env")
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    val = _strip_inline_comment(val).strip()
                    os.environ.setdefault(key.strip(), val)
    except FileNotFoundError:
        pass


def _strip_inline_comment(val: str) -> str:
    """값에서 인라인 주석(`val   # comment`)을 제거한다.

    앞에 공백이 있는 `#` 부터를 주석으로 본다 — `ap-northeast-2  # 서울` → `ap-northeast-2`.
    공백 없는 `#`(`pw#123`)은 정당한 값 일부로 보고 보존한다 (#24).
    """
    for i, ch in enumerate(val):
        if ch == "#" and i > 0 and val[i - 1] in " \t":
            return val[:i]
    return val
