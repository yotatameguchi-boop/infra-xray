"""Package tracked sources, the built UI, and wheels without local data."""
import hashlib
import os
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
version = re.search(r'__version__ = "([^"]+)"', (ROOT / 'infra_xray/__init__.py').read_text()).group(1)
if os.environ.get('GITHUB_REF_TYPE') == 'tag':
    assert os.environ.get('GITHUB_REF_NAME') == 'v' + version, 'Tag and package versions differ'
dist = ROOT / 'dist'
dist.mkdir(exist_ok=True)
wheel = dist / ('infra_xray-' + version + '-py3-none-any.whl')
assert wheel.is_file(), 'Build the wheel first: python -m build'
archive = dist / ('infra-xray-' + version + '.zip')
tracked = set(filter(None, subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')))
# Include rebuilt hashed UI assets even when their names changed in CI.
tracked.update(str(p.relative_to(ROOT)) for p in (ROOT / 'infra_xray/static').rglob('*') if p.is_file())
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as output:
    for name in sorted(filter(None, tracked)):
        path = ROOT / name
        if path.is_file():
            output.write(path, 'infra-xray/' + name)
    output.write(wheel, 'infra-xray/dist/' + wheel.name)
artifacts = sorted(p for p in dist.iterdir() if p.is_file() and p.suffix in ('.whl', '.gz', '.zip'))
(dist / 'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name + '\n' for p in artifacts))
print('Packaged Infra X-Ray ' + version)
