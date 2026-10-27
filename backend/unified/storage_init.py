"""Prepare empty writable directories before dropping container privileges."""

import os
import sys
from pathlib import Path


def initialize(directory: Path) -> bool:
    # Work through the opened directory, never traverse or change its contents.
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        if os.fstat(fd).st_uid != 0 or os.listdir(fd):
            return False
        os.fchown(fd, 10001, 10001)
        os.fchmod(fd, 0o700)
        return True
    finally:
        os.close(fd)


def main() -> None:
    for variable, default in (("DATA_DIR", "/data"), ("SOURCE_DIR", "/sources")):
        directory = Path(os.environ.get(variable, default))
        directory.mkdir(parents=True, exist_ok=True)
        changed = initialize(directory)
        print(f"{directory}: {'initialized' if changed else 'existing directory preserved'}",
              file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
