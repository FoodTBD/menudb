import collections
import csv
from collections import defaultdict
from typing import Any

from model import KnownTermsDB

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


# def _generate_partitions(input_string: str) -> list[list[str]]:
#     """
#     Input: "AAA"
#     Output: [['A', 'B', 'C'], ['A', 'BC'], ['AB', 'C'], ['ABC']]
#     """
#     n = len(input_string)
#     results = []

#     # Iterate over all possible combinations of splitting points
#     for split_points in itertools.product([True, False], repeat=n - 1):
#         split_points = (
#             False,
#         ) + split_points  # Add a False at the start for correct indexing
#         partition = []
#         current_partition = input_string[0]

#         for i in range(1, n):
#             if split_points[i]:
#                 # If True, start a new partition
#                 partition.append(current_partition)
#                 current_partition = input_string[i]
#             else:
#                 # If False, continue the current partition
#                 current_partition += input_string[i]

#         partition.append(current_partition)  # Add the last partition
#         results.append(partition)

#     return results


def gather_menu_stats(
    menu_yaml_dicts: list[dict[str, Any]], db: KnownTermsDB
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

    def _enrich_counter_tuple_with_en(t: tuple) -> tuple:
        word, n = t

        known_term = db.known_terms_lookup_dict.get(word)
        if known_term:
            en = f'"{known_term.name_en}"'
        else:
            terms_en = []
            for i, c in enumerate(word):
                known_term = db.known_terms_lookup_dict.get(c)
                if known_term:
                    en = f'"{known_term.name_en}"'
                else:
                    known_term = db.find_known_term(c, (i == len(word) - 1), (i == 0))
                    if known_term:
                        en = f'part of "{known_term.name_en}"'
                    else:
                        en = f'"{UNKNOWN_CHAR_PLACEHOLDER}"'
                terms_en.append(en)

            en = " + ".join(terms_en)

        return (word, n, en)

    # Enrich tuples with English definitions
    top_characters_not_known = []
    top_character_tuples = []
    for c, n in character_counter.most_common(350):
        if c.isalpha():
            t = _enrich_counter_tuple_with_en((c, n))
            top_character_tuples.append(t)

    if top_characters_not_known:
        print(f"Top characters not present in known_terms: {top_characters_not_known}")

    # Get primary names with non-alpha characters filtered out
    alpha_primary_names = []
    for name in set(menu_item_primary_names):
        name = "".join([c if c.isalpha() else " " for c in name])
        alpha_primary_names.extend(name.split(" "))

    # Find top 2-grams
    top_2gram_tuples = []
    for word, n in find_top_ngrams(alpha_primary_names, 2, 100):
        # Filter out low-frequency results
        if n < 3:
            continue
        t = _enrich_counter_tuple_with_en((word, n))
        top_2gram_tuples.append(t)

    # Find top 3-grams
    top_3gram_tuples = []
    for word, n in find_top_ngrams(alpha_primary_names, 3, 100):
        # Filter out low-frequency results
        if n < 3:
            continue
        t = _enrich_counter_tuple_with_en((word, n))
        top_3gram_tuples.append(t)

    # Find common dishes
    menu_item_primary_name_counter = collections.Counter(menu_item_primary_names)
    filtered_c = {k: v for k, v in menu_item_primary_name_counter.items() if v >= 3}
    common_dishes = []
    for k, v in sorted(filtered_c.items(), key=lambda x: x[1], reverse=True):
        known_term = db.known_terms_lookup_dict.get(k)
        if known_term:
            en = known_term.name_en
        else:
            en = UNKNOWN_CHAR_PLACEHOLDER
        t = (k, v, en)
        common_dishes.append(t)

    # Data linting
    for dish_name in filtered_c:
        if not dish_name in db.known_dish_lookup_dict.keys():
            print(
                f"WARNING: {dish_name} (count {menu_item_primary_name_counter[dish_name]}) is not in known_dishes"
            )

    eatsdb_names_set = set(load_eatsdb_names())
    for dish_name in menu_item_primary_names:
        if (
            not dish_name in db.known_dish_lookup_dict.keys()
            and dish_name in eatsdb_names_set
        ):
            print(
                f"WARNING: {dish_name} (count {menu_item_primary_name_counter[dish_name]}) is not in known_dishes but is in EatsDB"
            )

    return {
        "menu_count": len(menu_yaml_dicts),
        "unique_menu_item_count": len(set(menu_item_primary_names)),
        "unique_character_count": len(character_counter),
        "top_characters": top_character_tuples,
        "top_2grams": top_2gram_tuples,
        "top_3grams": top_3gram_tuples,
        "common_dishes": common_dishes,
    }
