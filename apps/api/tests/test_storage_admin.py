import os
from uuid import uuid4

import pytest

from app.storage import LocalStorage


@pytest.mark.parametrize("parent", [False, True])
def test_symlink_cannot_read_or_quarantine_external_bytes(tmp_path, parent):
    storage = LocalStorage(tmp_path / "private")
    lead, file = str(uuid4()), str(uuid4())
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / file).write_bytes(b"outside-bytes")
    target = storage.root / "objects" / lead
    try:
        if parent:
            os.symlink(outside, target, target_is_directory=True)
        else:
            target.mkdir()
            os.symlink(outside / file, target / file)
    except OSError:
        pytest.skip("OS does not permit synthetic symlinks")
    key = f"objects/{lead}/{file}"
    for operation in (storage.read, storage.delete, storage.quarantine):
        with pytest.raises(ValueError):
            operation(key)
    assert (outside / file).read_bytes() == b"outside-bytes"
