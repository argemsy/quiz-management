from enum import Enum


class EnumChoices(Enum):
    @classmethod
    def choices(cls) -> tuple[tuple[str, int | str]]:
        return tuple((item.name, item.value) for item in cls)
