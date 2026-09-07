"""Re-queue CV originals from CV_Theque back to staging for watcher reprocessing."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from script.staging_watcher import WATCHER_STAGING_PATH, _make_sftp

REQUEUE = [
    "/sftp/cv_tech/files/CV_Theque/DevOps/Senior/originals/MBROUK_Rida_VF.pdf",
    "/sftp/cv_tech/files/CV_Theque/DevOps/Senior/originals/HAMZA_SHOUL VF.pdf",
    "/sftp/cv_tech/files/CV_Theque/DevOps/Senior/originals/CV_2026-02-02_Youssef_Chergaoui.pdf",
]


def main() -> None:
    sftp = _make_sftp()
    if not sftp.connect():
        raise SystemExit(f"SFTP connect failed: {sftp.last_error}")

    for remote_src in REQUEUE:
        name = remote_src.rsplit("/", 1)[-1]
        dst = f"{WATCHER_STAGING_PATH.rstrip('/')}/{name}"
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / name
            sftp._require_sftp().get(remote_src, str(local))
            if sftp.exists(dst):
                sftp.remove(dst)
            sftp.upload(local, dst)
        print(f"Re-queued {name} -> {dst}")


if __name__ == "__main__":
    main()
