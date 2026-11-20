"""Check the same geometry functions used by the browser, without a build step."""
from pathlib import Path
import shutil
import subprocess


def test_scatter_geometry():
    node = shutil.which('node')
    assert node, 'Node.js is required for the JavaScript unit checks.'
    subprocess.run([node, str(Path(__file__).with_name('scatter_unit.js'))], check=True)
