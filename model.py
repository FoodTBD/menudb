import dataclasses
import urllib.parse

EN_STOPWORDS = ["a", "an", "and", "BBQ", "for", "in", "with"]


@dataclasses.dataclass
class KnownTerm:
    native_name_dict: dict  # key is BCP 47 language tag; value MAY be CSV
    name_en: str
    wikipedia_url: str | None
    image_url: str | None
    description_en: str | None
    dish_cuisine_locale: str | None  # BCP 47 language tag

    _menu_filenames: list[str]

    def __init__(self, csv_row: dict[str, str]):
        # Load data from CSV format
        self.native_name_dict = {}
        for k in ["name_zh-Hans", "name_zh-Hant"]:
            self.native_name_dict[k] = csv_row.pop(k)
        for k, v in csv_row.items():
            if not k.startswith("_"):
                setattr(self, k, v)

        # Internal use properties
        self._menu_filenames = []

        # Check for duplicates
        for lang in ["name_zh-Hans", "name_zh-Hant"]:
            name_set = set()
            localized_name = self.native_name_dict.get(lang)
            if localized_name:
                if localized_name in name_set:
                    print(
                        f'WARNING: duplicate {lang} key "{localized_name}" in known_terms'
                    )
                name_set.add(localized_name)

        # Check capitalization
        if self.dish_cuisine_locale:
            en_actual = self.name_en
            en_expected = " ".join(
                [
                    w.title() if not w in EN_STOPWORDS and w.isalpha() else w
                    for w in en_actual.split(" ")
                ]
            )
            if en_actual != en_expected:
                print(
                    f"WARNING: {en_actual} defines dish_cuisine_locale but is not title cased"
                )

        # Rewrite non-English Wikipedia links to be presented via Google Translate
        if self.wikipedia_url:
            o = urllib.parse.urlparse(self.wikipedia_url)
            if o.hostname and not o.hostname.startswith("en."):
                self.wikipedia_url = (
                    "https://translate.google.com/translate?sl=auto&tl=en&u="
                    + self.wikipedia_url
                )

    def __hash__(self):
        return hash((str(self.native_name_dict), self.name_en))

    def __eq__(self, other):
        return (
            self.native_name_dict == other.native_name_dict
            and self.name_en == other.name_en
        )

    @property
    def primary_lang(self) -> str:
        return list(self.native_name_dict.keys())[0]

    @property
    def name_primary(self) -> str:
        return self.native_name_dict[self.primary_lang]

    @property
    def all_native_names(self) -> list[str]:
        all_native_names = []
        for v in self.native_name_dict.values():
            all_native_names.extend([s.strip() for s in v.split(",") if s.strip()])
        return all_native_names
