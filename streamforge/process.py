from collections import deque
import os
import queue
import subprocess
import threading
from pathlib import Path
from typing import Callable
import imageio_ffmpeg

class Cancelled(Exception):
    pass

def check_cancel(cancel: threading.Event) -> None:
    if cancel.is_set():
        raise Cancelled("Операция отменена")

def ffmpeg() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()

def run_ffmpeg(arguments: list[str], duration: float, cancel: threading.Event,
               progress: Callable[[float], None] = lambda _: None, cwd: Path | None = None) -> None:
    """Consume both diagnostics and real FFmpeg timestamps without blocking cancellation."""
    check_cancel(cancel)
    command = [ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "warning", "-progress", "pipe:1", "-nostats", *arguments]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding="utf-8", errors="replace", cwd=cwd,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    lines: queue.Queue[str | None] = queue.Queue()
    def read():
        try:
            for line in process.stdout:
                lines.put(line.rstrip())
        finally:
            lines.put(None)
    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    diagnostics: deque[str] = deque(maxlen=30)
    try:
        while True:
            check_cancel(cancel)
            try:
                line = lines.get(timeout=.15)
            except queue.Empty:
                continue
            if line is None:
                break
            diagnostics.append(line)
            if line.startswith("out_time_us="):
                try:
                    progress(min(.999, max(0, int(line.split("=", 1)[1]) / 1_000_000 / max(duration, .001))))
                except ValueError:
                    pass
        returncode = process.wait()
        if returncode:
            raise RuntimeError("FFmpeg завершился с ошибкой:\n" + "\n".join(diagnostics))
        progress(1)
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        reader.join(timeout=3)
        process.stdout.close()
