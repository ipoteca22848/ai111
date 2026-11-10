"""Expose test failure details as annotations, even when CI logs require login."""
from pathlib import Path
import subprocess
import sys

result = subprocess.run([sys.executable, '-m', 'pytest', '-q', '--tb=short'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, encoding='utf-8', errors='replace', env=__import__('os').environ | {'PYTHONIOENCODING': 'utf-8'})
print(result.stdout)
Path('build').mkdir(exist_ok=True)
Path('build/pytest.log').write_text(result.stdout, encoding='utf-8')
if result.returncode:
    message=result.stdout[-18000:].replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
    print('::error title=Windows test diagnostics::' + message)
raise SystemExit(result.returncode)
