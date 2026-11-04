#!/usr/bin/env python3
"""서비스 간 계약 묶음을 만든다(ADR-0013).

    python3 scripts/package-service-contracts.py <출력 폴더>

같은 내용이면 언제 어디서 만들어도 같은 바이트가 나오도록 파일 순서·시각·소유자·권한을
고정한다. 묶음 SHA-256을 쓰는 쪽 잠금 파일에 적기 때문이다.
"""

import gzip
import hashlib
import io
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# 원본을 루트 service-contracts/로 옮기면 여기만 바꾼다. 묶음 안 최상위 폴더 이름은 그대로다.
SOURCE = ROOT / "docs" / "contracts"
ARCHIVE_ROOT = "service-contracts"


def _version() -> str:
    return (SOURCE / "VERSION").read_text(encoding="utf-8").strip()


def _files() -> list[Path]:
    # 작업 공간에만 있는 파일(.DS_Store 등)이 섞이지 않게 git이 추적하는 파일만 넣는다.
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--", str(SOURCE)],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout.decode("utf-8")
    return sorted(ROOT / name for name in listed.split("\0") if name)


def _tar_bytes() -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for path in _files():
            data = path.read_bytes()
            info = tarfile.TarInfo(f"{ARCHIVE_ROOT}/{path.relative_to(SOURCE).as_posix()}")
            info.size = len(data)
            info.mtime = 0
            info.mode = 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            tar.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: package-service-contracts.py <출력 폴더>")
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    version = _version()
    archive = out / f"{ARCHIVE_ROOT}-{version}.tar.gz"
    compressed = io.BytesIO()
    # gzip 머리에 시각과 파일 이름이 들어가면 같은 내용도 다른 바이트가 된다.
    with gzip.GzipFile(filename="", mode="wb", fileobj=compressed, mtime=0) as gz:
        gz.write(_tar_bytes())
    archive.write_bytes(compressed.getvalue())
    digest = hashlib.sha256(compressed.getvalue()).hexdigest()
    (out / f"{archive.name}.sha256").write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    print(archive)


if __name__ == "__main__":
    main()
