"""Download the official multilingual Tiny model and record its exact upstream revision."""
import json
from pathlib import Path
from huggingface_hub import HfApi, snapshot_download

root = Path(__file__).resolve().parent.parent
repository = 'Systran/faster-whisper-tiny'
revision = HfApi().model_info(repository).sha
folder = root / 'assets' / 'model'
snapshot_download(repository, revision=revision, local_dir=folder,
                  allow_patterns=['config.json', 'preprocessor_config.json', 'model.bin', 'tokenizer.json', 'vocabulary.*'])
for filename in ('config.json', 'model.bin', 'tokenizer.json'):
    if not (folder / filename).is_file():
        raise RuntimeError('Incomplete model: ' + filename)
(folder / 'provenance.json').write_text(json.dumps({'repository': repository, 'revision': revision}, indent=2), encoding='utf-8')
# Download bookkeeping is not needed by the frozen application.
import shutil
shutil.rmtree(folder / '.cache', ignore_errors=True)
print('Prepared model:', repository, revision)
