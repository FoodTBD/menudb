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
        # Build native_name_dict from all name_* fields except en
        self.native_name_dict = {}
        native_name_keys = [
            k for k in csv_row.keys() if k.startswith("name_") and k != "name_en"
        ]
        for k in native_name_keys:
            self.native_name_dict[k] = csv_row.pop(k)

        for k, v in csv_row.items():
            # Ignore fields with underscore names
            if not k.startswith("_"):
                setattr(self, k, v)

        # Internal use properties
        self._menu_filenames = []

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


@dataclasses.dataclass
class KnownTermsDB:
    # All rows in known_terms.tsv
    known_terms: list[KnownTerm]

    # Mapping of native name to KnownTerm
    known_terms_lookup_dict: dict[str, KnownTerm]

    # Subset of known_terms where dish_cuisine_locale is set
    known_dishes: list[KnownTerm]

    # Mapping of native name to dish object (which is a KnownTerm)
    known_dish_lookup_dict: dict[str, KnownTerm]

    def __init__(self, known_terms: list[KnownTerm]):
        self.known_terms = known_terms

        # Look for duplicates and warn
        for lang in known_terms[0].native_name_dict.keys():
            name_set = set()
            for known_term in known_terms:
                name = known_term.native_name_dict[lang]
                if name:
                    if name in name_set:
                        print(f'WARNING: duplicate {lang} key "{name}" in known_terms')
                    name_set.add(name)

        # Build known_terms_lookup_dict using all native names
        self.known_terms_lookup_dict = {}
        for known_term in self.known_terms:
            self.known_terms_lookup_dict.update(
                {native_name: known_term for native_name in known_term.all_native_names}
            )

        # Build list of known_dishes
        self.known_dishes = []
        for known_term in self.known_terms:
            if known_term.dish_cuisine_locale:
                self.known_dishes.append(known_term)

        # Build known_dish_lookup_dict using all native names
        self.known_dish_lookup_dict = {}
        for known_dish in self.known_dishes:
            self.known_dish_lookup_dict.update(
                {native_name: known_dish for native_name in known_dish.all_native_names}
            )

    def find_known_term(
        self, substr: str, startswith: bool = False, endswith: bool = False
    ) -> KnownTerm | None:
        found_known_term = None
        for k, v in self.known_terms_lookup_dict.items():
            found = False
            if startswith and k.startswith(substr):
                found = True
            elif endswith and k.endswith(substr):
                found = True
            elif substr in k:
                found = True

            if found:
                if not found_known_term or len(v.name_en) < len(
                    found_known_term.name_en
                ):
                    found_known_term = v
        return found_known_term
