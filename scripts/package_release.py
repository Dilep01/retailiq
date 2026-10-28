"""Package only Git-indexed source; fail closed on runtime/private paths."""

import hashlib
import subprocess
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parent.parent
paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0")
target = root / "dist/retailiq-v1.0.0-source.zip"
target.parent.mkdir(exist_ok=True)
if not any(paths):
    raise SystemExit("Stage reviewed source files in Git before packaging.")
with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
    for name in paths:
        if not name:
            continue
        if (
            name.split("/")[0] in [".runtime", ".venv", ".git", "dist"]
            or name == ".env"
            or name.endswith((".sqlite3", ".joblib"))
        ):
            raise SystemExit(f"Private/runtime file unexpectedly indexed: {name}")
        archive.write(root / name, "retailiq/" + name)
(target.with_suffix(".zip.sha256")).write_text(
    hashlib.sha256(target.read_bytes()).hexdigest() + "  " + target.name + "\n"
)
print(f"Created {target.name}; {len(paths) - 1} source files; SHA-256 saved alongside.")
