import collections
import csv
from collections import defaultdict
import itertools
from typing import Any

from model import KnownTerm

UNKNOWN_CHAR_PLACEHOLDER = "🟨"


def _generate_ngrams(text: str, n: int) -> list[str]:
    ngrams = []
    for i in range(len(text) - n + 1):
        ngram = text[i : i + n]
        ngrams.append(ngram)
    return ngrams


def find_top_ngrams(
    strings: list[str], n: int, top_n: int = 10
) -> list[tuple[str, int]]:
    ngram_counts = defaultdict(int)
    for string in strings:
        ngrams = _generate_ngrams(string, n)
        for ngram in ngrams:
            ngram_counts[ngram] += 1

    # Get the top n-grams
    sorted_ngrams = sorted(ngram_counts.items(), key=lambda x: x[1], reverse=True)
    top_ngrams = sorted_ngrams[:top_n]

    return top_ngrams


def load_eatsdb_names() -> list[str]:
    dish_names = []
    with open("data/eatsdb_names.tsv", "r", encoding="utf-8") as csvfile:
        csvreader = csv.DictReader(csvfile, delimiter="\t")
        for row in csvreader:
            assert row["name_native"]
            dish_names.append(row["name_native"])
            dish_names.extend(
                [s.strip() for s in row["alt_names"].split(",") if s.strip()]
            )
    return dish_names


def _generate_partitions(input_string: str) -> list[list[str]]:
    """
    Input: "AAA"
    Output: [['A', 'B', 'C'], ['A', 'BC'], ['AB', 'C'], ['ABC']]
    """
    n = len(input_string)
    results = []

    # Iterate over all possible combinations of splitting points
    for split_points in itertools.product([True, False], repeat=n - 1):
        split_points = (
            False,
        ) + split_points  # Add a False at the start for correct indexing
        partition = []
        current_partition = input_string[0]

        for i in range(1, n):
            if split_points[i]:
                # If True, start a new partition
                partition.append(current_partition)
                current_partition = input_string[i]
            else:
                # If False, continue the current partition
                current_partition += input_string[i]

        partition.append(current_partition)  # Add the last partition
        results.append(partition)

    return results


def gather_menu_stats(
    menu_yaml_dicts: list[dict[str, Any]],
    known_terms: list[KnownTerm],
    known_terms_lookup_dict: dict[str, KnownTerm],
    known_dish_lookup_dict: dict[str, KnownTerm],
) -> dict[str, Any]:
    # Find dish names
    menu_item_primary_names = []
    for menu_yaml_dict in menu_yaml_dicts:
        if menu_yaml_dict.get("menu"):
            menu = menu_yaml_dict["menu"]
            primary_lang = menu["language_codes"][0]
            menu_primary_name_set = set()
            for page in menu["pages"]:
                if page.get("sections"):
                    for section in page["sections"]:
                        if section.get("menu_items"):
                            for menu_item in section["menu_items"]:
                                name_lang = "name_" + primary_lang
                                if menu_item.get(name_lang):
                                    primary_name = menu_item[name_lang]
                                    menu_primary_name_set.add(primary_name)
            menu_item_primary_names.extend(menu_primary_name_set)

    # Find top alphabetic characters
    character_counter = collections.Counter()
    for primary_name in menu_item_primary_names:
        character_counter.update("".join([c for c in primary_name if c.isalpha()]))

    top_characters = character_counter.most_common(250)
    top_chars_not_known = []
    for tuple in top_characters:
        if (
            tuple[0] not in "".join(known_terms_lookup_dict.keys())
            and tuple[0].isalpha()
        ):
            top_chars_not_known.append(tuple[0])
    if top_chars_not_known:
        print(f"Top characters not present in known_terms: {top_chars_not_known}")

    top_characters = character_counter.most_common(50)
    # Enrich tuples with English definitions
    top_characters = []
    for k, v in top_characters:
        known_term = known_terms_lookup_dict.get(k)
        if known_term:
            en = known_term.name_en
        else:
            en = UNKNOWN_CHAR_PLACEHOLDER
        t = (k, v, en)
        top_characters.append(t)

    # Get primary names with non-alpha characters filtered out
    alpha_primary_names = []
    for name in set(menu_item_primary_names):
        name = "".join([c if c.isalpha() else " " for c in name])
        alpha_primary_names.extend(name.split(" "))

    # Find top 3-grams
    top_3gram_tuples = []
    for ngram, count in find_top_ngrams(alpha_primary_names, 3, 50):
        # Filter out low-frequency results
        if count < 3:
            continue

        # Enrich tuples with English definitions
        best_en = None
        for terms_zh in _generate_partitions(ngram):
            terms_en = []
            for term_zh in terms_zh:
                known_term = known_terms_lookup_dict.get(term_zh)
                if known_term:
                    en = known_term.name_en
                else:
                    en = None
                terms_en.append(en)
            en = " + ".join(
                [f'"{s}"' if s else f'"{UNKNOWN_CHAR_PLACEHOLDER}"' for s in terms_en]
            )
            if any(terms_en):
                best_en = en
            if all(terms_en):
                break
        t = (ngram, count, best_en)
        top_3gram_tuples.append(t)

    top_3grams = [t[0] for t in top_3gram_tuples]

    # Find top 2-grams
    top_2gram_tuples = []
    for k, v in find_top_ngrams(alpha_primary_names, 2, 200):
        if v >= 3:
            # Enrich tuples with English definitions
            known_term = known_terms_lookup_dict.get(k)
            if known_term:
                en = known_term.name_en
            else:
                en = None

            if en:
                en = f'"{en}"'
            else:
                terms_en = []
                for c in k:
                    known_term = known_terms_lookup_dict.get(c)
                    if known_term:
                        en = known_term.name_en
                    else:
                        en = UNKNOWN_CHAR_PLACEHOLDER
                    terms_en.append(en)

                en = " + ".join([f'"{en}"' for en in terms_en])
            t = (k, v, en)

            # Filter out 2-grams e.g. "黃毛" that are included in 3-grams e.g. "黃毛雞"
            is_included = False
            for three_gram in top_3grams:
                if k in three_gram:
                    is_included = True
                    break

            if not is_included:
                top_2gram_tuples.append(t)

    # Find common dishes
    menu_item_primary_name_counter = collections.Counter(menu_item_primary_names)
    filtered_c = {k: v for k, v in menu_item_primary_name_counter.items() if v >= 3}
    common_dishes = []
    for k, v in sorted(filtered_c.items(), key=lambda x: x[1], reverse=True):
        known_term = known_terms_lookup_dict.get(k)
        if known_term:
            en = known_term.name_en
        else:
            en = UNKNOWN_CHAR_PLACEHOLDER
        t = (k, v, en)
        common_dishes.append(t)

    # Data linting
    for dish_name in filtered_c:
        if not dish_name in known_dish_lookup_dict.keys():
            print(
                f"WARNING: {dish_name} (count {menu_item_primary_name_counter[dish_name]}) is not in known_dishes"
            )

    eatsdb_names_set = set(load_eatsdb_names())
    for dish_name in menu_item_primary_names:
        if (
            not dish_name in known_dish_lookup_dict.keys()
            and dish_name in eatsdb_names_set
        ):
            print(
                f"WARNING: {dish_name} (count {menu_item_primary_name_counter[dish_name]}) is not in known_dishes but is in EatsDB"
            )

    return {
        "menu_count": len(menu_yaml_dicts),
        "unique_menu_item_count": len(set(menu_item_primary_names)),
        "unique_character_count": len(character_counter),
        "top_characters": top_characters,
        "top_2grams": top_2gram_tuples,
        "top_3grams": top_3gram_tuples,
        "common_dishes": common_dishes,
    }
