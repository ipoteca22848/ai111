from pathlib import Path
from streamforge.models import Segment


def ass_time(seconds: float) -> str:
    ticks = max(0, round(seconds * 100))
    return f"{ticks // 360000}:{ticks // 6000 % 60:02d}:{ticks // 100 % 60:02d}.{ticks % 100:02d}"


def escape(text: str) -> str:
    return text.replace("\\", "／").replace("{", "（").replace("}", "）").replace("\n", " ").replace("\r", " ")


def make_ass(path: Path, segments: list[Segment], start: float, end: float,
             width: int, height: int, banner_height: int, hook: str = "") -> None:
    size = round(width * .055)
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,DejaVu Sans,{size},&H0088FF39,&H00FFFFFF,&H00101010,&H90000000,-1,0,0,0,100,100,0,0,1,2,1,2,35,35,{banner_height + round(height * .08)},1
Style: Hook,DejaVu Sans,{round(size * .85)},&H00FFFFFF,&H00FFFFFF,&H00101010,&H90000000,-1,0,0,0,100,100,0,0,1,2,1,8,35,35,{round(height * .09)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for segment in segments:
        selected = [word for word in segment.words if word.end > start and word.start < end]
        if not selected and not segment.words and segment.end > start and segment.start < end:
            events.append(f"Dialogue: 0,{ass_time(max(0, segment.start-start))},{ass_time(min(end-start, segment.end-start))},Caption,,0,0,0,,{escape(segment.text)}")
        for offset in range(0, len(selected), 4):
            words = selected[offset:offset+4]
            begin, finish = max(start, words[0].start), min(end, words[-1].end)
            if finish <= begin:
                continue
            tokens = []
            cursor = begin
            for word in words:
                gap = max(0, min(end, word.start) - cursor)
                if gap:
                    tokens.append("{\\k" + str(round(gap * 100)) + "}")
                ticks = max(1, round((min(end, word.end) - max(start, word.start)) * 100))
                tokens.append("{\\kf" + str(ticks) + "}" + escape(word.text))
                cursor = min(end, word.end)
            events.append(f"Dialogue: 0,{ass_time(begin-start)},{ass_time(finish-start)},Caption,,0,0,0,,{' '.join(tokens)}")
    if hook.strip():
        events.append(f"Dialogue: 1,0:00:00.00,{ass_time(min(5, end-start))},Hook,,0,0,0,,{escape(hook[:140])}")
    path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
