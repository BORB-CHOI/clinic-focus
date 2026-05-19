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
                    os.environ.setdefault(key.strip(), val.strip())
    except FileNotFoundError:
        pass
