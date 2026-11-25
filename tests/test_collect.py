import pytest
from magbench import collect


def test_collection_requires_linux_procfs_before_reading_launch(tmp_path, monkeypatch):
    monkeypatch.setattr(collect.sys, 'platform', 'darwin')
    with pytest.raises(RuntimeError, match='requires Linux procfs'):
        collect.collect(tmp_path, tmp_path)
