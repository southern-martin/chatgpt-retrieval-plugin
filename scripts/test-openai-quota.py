#!/usr/bin/env python3
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def load_env_file(path: Path) -> bool:
    if not path.exists():
        return False
    found_key = False
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip().lstrip("\ufeff")
        if key.startswith("export "):
            key = key[len("export ") :].strip()
        if key in os.environ:
            continue
        val = val.strip().strip('"').strip("'")
        os.environ[key] = val
        if key == "OPENAI_API_KEY":
            found_key = True
    return found_key


def main() -> int:
    env_paths = []
    found_in_env = False

    env_file = os.environ.get("ENV_FILE")
    if env_file:
        path = Path(env_file)
        env_paths.append(path)
        found_in_env = load_env_file(path) or found_in_env

    cwd_env = Path.cwd() / ".env"
    env_paths.append(cwd_env)
    found_in_env = load_env_file(cwd_env) or found_in_env

    repo_env = Path(__file__).resolve().parents[1] / ".env"
    env_paths.append(repo_env)
    found_in_env = load_env_file(repo_env) or found_in_env

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        checked = [str(p) for p in env_paths if p.exists()]
        if checked:
            print("ERROR: OPENAI_API_KEY is not set. Checked:", ", ".join(checked))
        else:
            print("ERROR: OPENAI_API_KEY is not set. No .env file found.")
        return 1

    model = os.environ.get("MODEL", os.environ.get("EMBEDDING_MODEL", "text-embedding-3-large"))
    text = os.environ.get("INPUT", "test")
    url = os.environ.get("OPENAI_API_URL", "https://api.openai.com/v1/embeddings")

    payload = {"model": model, "input": text}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
        data = json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"HTTP {e.code}: {body}")
        return 1
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

    usage = data.get("usage")
    embedding_len = None
    try:
        embedding_len = len(data["data"][0]["embedding"])
    except Exception:
        pass

    print("OK: embeddings request succeeded")
    if usage:
        print("usage:", usage)
    if embedding_len is not None:
        print("embedding_dim:", embedding_len)
    return 0


if __name__ == "__main__":
    sys.exit(main())
