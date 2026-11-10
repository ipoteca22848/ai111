from dataclasses import asdict, dataclass, field

@dataclass
class Word:
    start: float
    end: float
    text: str

@dataclass
class Segment:
    start: float
    end: float
    text: str
    words: list[Word] = field(default_factory=list)

@dataclass
class Clip:
    start: float
    end: float
    score: int
    title: str
    reason: str
    output: str = ""
    status: str = "Ожидает"

@dataclass
class Options:
    count: int = 5
    length: int = 30
    width: int = 720
    height: int = 1280
    fps: int = 30
    mode: str = "blur"
    speech: bool = True
    subtitles: bool = True
    language: str = "auto"
    device: str = "cpu"
    banner: str = ""
    banner_image: str = ""
    hook: str = ""
    output_dir: str = ""

    def validate(self) -> None:
        if not 1 <= self.count <= 20 or not 10 <= self.length <= 180:
            raise ValueError("Количество: 1–20; длительность: 10–180 секунд")
        if (self.width, self.height) not in ((360, 640), (720, 1280), (1080, 1920)):
            raise ValueError("Неизвестное разрешение")
        if self.mode not in ("blur", "crop", "fit") or self.fps not in (30, 60):
            raise ValueError("Некорректные настройки экспорта")
        if self.device not in ("cpu", "cuda") or self.language not in ("auto", "ru", "en"):
            raise ValueError("Некорректные настройки распознавания")
        if self.banner_image:
            from pathlib import Path
            if not Path(self.banner_image).is_file():
                raise ValueError("Изображение баннера не найдено")
        if not self.output_dir:
            raise ValueError("Выберите папку экспорта")

def segment_from_dict(data: dict) -> Segment:
    return Segment(data["start"], data["end"], data["text"], [Word(**word) for word in data.get("words", [])])
