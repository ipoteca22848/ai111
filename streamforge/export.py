import threading
import shutil
import uuid
from pathlib import Path
from typing import Callable
from streamforge.banner import make_banner
from streamforge.config import resources
from streamforge.models import Clip, Options, Segment
from streamforge.process import run_ffmpeg, check_cancel
from streamforge.subtitles import make_ass



def render_clip(source: str, clip: Clip, segments: list[Segment], options: Options,
                folder: Path, cancel: threading.Event, progress: Callable[[float], None],
                output: Path) -> Path:
    options.validate()
    check_cancel(cancel)
    if clip.end <= clip.start or clip.start < 0:
        raise ValueError("Некорректный диапазон клипа")
    width, height = options.width, options.height
    banner_height = round(height * .13 / 2) * 2 if options.banner.strip() or options.banner_image else 0
    args = ["-y", "-ss", str(clip.start), "-i", str(Path(source).resolve())]
    if banner_height:
        banner_path = folder / "banner.png"
        make_banner(banner_path, width, banner_height, options.banner, options.banner_image)
        args += ["-i", str(banner_path.resolve())]
    if options.mode == "blur":
        filters = (f"[0:v]split=2[bg][fg];[bg]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},gblur=sigma=24[background];"
                   f"[fg]scale={width}:{height}:force_original_aspect_ratio=decrease[foreground];"
                   "[background][foreground]overlay=(W-w)/2:(H-h)/2[base]")
    elif options.mode == "crop":
        filters = f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}[base]"
    else:
        filters = f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2[base]"
    current = "base"
    if banner_height:
        filters += f";[base][1:v]overlay=0:{height-banner_height}[bannered]"
        current = "bannered"
    if (options.subtitles and segments) or options.hook.strip():
        subtitle_path = folder / "captions.ass"
        make_ass(subtitle_path, segments if options.subtitles else [], clip.start, clip.end, width, height, banner_height, options.hook or clip.title)
        shutil.copytree(resources() / "fonts", folder / "fonts", dirs_exist_ok=True)
        filters += f";[{current}]ass=filename=captions.ass:fontsdir=fonts[captioned]"
        current = "captioned"
    filters += f";[{current}]setsar=1,format=yuv420p[out]"
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_name(output.stem + "." + uuid.uuid4().hex[:8] + ".partial.mp4")
    try:
        run_ffmpeg([*args, "-filter_complex_threads", "2", "-filter_complex", filters,
                    "-t", str(clip.end-clip.start), "-map", "[out]", "-map", "0:a:0?", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-threads", "4",
                    "-r", str(options.fps), "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(partial.resolve())],
                   clip.end-clip.start, cancel, progress, cwd=folder)
        check_cancel(cancel)
        partial.replace(output)
    finally:
        partial.unlink(missing_ok=True)
    return output
