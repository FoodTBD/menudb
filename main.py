import collections
import csv
import datetime
import os
import shutil
import sys
import typing
import urllib.parse
from typing import Any, OrderedDict

import strictyaml
from jinja2 import Environment, FileSystemLoader

import jinja_filters
from ngrams import find_top_ngrams
from schema import RESTAURANT_SCHEMA

STATIC_DIR = "static"
INPUT_DIR = "content"
OUTPUT_DIR = "output"


def prepare_output_dir(output_dir: str) -> None:
    os.makedirs(output_dir, exist_ok=True)

    # cp -r ./static/ -> ./output/static/
    output_static_dir = os.path.join(output_dir, STATIC_DIR)
    if os.path.exists(output_static_dir):
        shutil.rmtree(output_static_dir)

    shutil.copytree(STATIC_DIR, output_static_dir)


def load_known_locales() -> dict[str, dict[str, Any]]:
    known_locales = []
    with open("data/known_locales.tsv", "r", encoding="utf-8") as csvfile:
        csvreader = csv.DictReader(csvfile, delimiter="\t")
        for row in csvreader:
            assert any(row.values()), "ERROR: known_locales has empty lines"
            known_locales.append(row)

    # Map locale_code to locale dict
    known_dish_lookuptable = {}
    for known_locale in known_locales:
        locale_code = known_locale["locale_code"]
        known_dish_lookuptable[locale_code] = known_locale
    return known_dish_lookuptable


def load_known_terms() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    known_terms = []
    with open("data/known_terms.tsv", "r", encoding="utf-8") as csvfile:
        csvreader = csv.DictReader(csvfile, delimiter="\t")
        for row in csvreader:
            assert any(row.values()), "ERROR: known_terms has empty lines"

            # Remove comments
            for k in list(row.keys()):
                if k.startswith("_"):
                    row.pop(k)

            # Rewrite non-English Wikipedia links to be presented via Google Translate
            wikipedia_url = row["wikipedia_url"]
            o = urllib.parse.urlparse(wikipedia_url)
            if o.hostname and not o.hostname.startswith("en."):
                row["wikipedia_url"] = (
                    "https://translate.google.com/translate?sl=auto&tl=en&u="
                    + wikipedia_url
                )

            known_terms.append(row)

    # Check for duplicates
    zh_hans_name_set = set()
    zh_hant_name_set = set()
    for known_term in known_terms:
        k = "zh-Hans"
        if known_term[k]:
            if known_term[k] in zh_hans_name_set:
                print(f'WARNING: duplicate {k} key "{known_term[k]}" in known_terms')
            zh_hans_name_set.add(known_term[k])

        k = "zh-Hant"
        if known_term[k]:
            if known_term[k] in zh_hant_name_set:
                print(f'WARNING: duplicate {k} key "{known_term[k]}" in known_terms')
            zh_hant_name_set.add(known_term[k])

    # Check capitalization
    EN_STOPWORDS = ["a", "an", "and", "BBQ", "for", "in", "with"]
    for known_term in known_terms:
        if known_term["dish_cuisine"]:
            en_actual = known_term["en"]
            en_expected = " ".join(
                [
                    w.title() if not w in EN_STOPWORDS and w.isalpha() else w
                    for w in en_actual.split(" ")
                ]
            )
            if en_actual != en_expected:
                print(
                    f'WARNING: {known_term["en"]} defines dish_cuisine but is not title cased'
                )

    known_terms_lookup_dict = {}
    for known_term in known_terms:
        # Use all native forms (both simplified and traditional) as lookup keys
        for k in ["zh-Hans", "zh-Hant"]:
            names = [s.strip() for s in known_term[k].split(",")]
            for name in names:
                if name:
                    known_terms_lookup_dict[name] = known_term

    known_dishes = []
    for known_term in known_terms:
        if known_term["dish_cuisine"]:
            # Backward compatiblity from known_terms to known_dishes
            known_dish = known_term.copy()
            known_dish["name_native"] = ",".join(
                [known_dish["zh-Hans"], known_dish["zh-Hant"]]
            )
            known_dish["name_en"] = known_dish.pop("en")
            known_dish["description_en"] = known_dish.pop("dish_description_en")
            known_dish["locale_code"] = known_dish.pop("dish_cuisine")
            known_dishes.append(known_dish)
    return known_terms_lookup_dict, known_dishes


def _slugify(s: str) -> str:
    return "".join([c if c.isalnum() else "-" for c in s])


def generate_menu_html(
    input_yaml_path: str,
    output_html_path: str,
    known_dish_lookuptable: dict[str, dict[str, Any]],
    known_terms_lookup_dict: dict[str, Any],
) -> dict[str, Any]:
    with open(input_yaml_path, "r", encoding="utf-8") as yaml_path:
        yaml_data = strictyaml.load(yaml_path.read(), RESTAURANT_SCHEMA)

    # Inject the modification date into the YAML data
    mod_date = datetime.datetime.fromtimestamp(os.path.getmtime(input_yaml_path))
    # The type checker thinks yaml_data.data is a str, not a dict
    yaml_dict = typing.cast(OrderedDict[str, Any], yaml_data.data)
    yaml_dict["_date_modified"] = mod_date.isoformat()

    # Inject restaurant.googlemaps_url if not already defined
    restaurant_dict = yaml_dict["restaurant"]
    if not restaurant_dict.get("googlemaps_url"):
        query = ", ".join(
            [
                restaurant_dict["name"],
                restaurant_dict["street_address"],
                restaurant_dict["city"],
                restaurant_dict["country_code"],
            ]
        )
        url = "https://www.google.com/maps/search/" + urllib.parse.quote(query)
        restaurant_dict["googlemaps_url"] = url

    if yaml_dict.get("menu"):
        primary_lang = yaml_dict["menu"]["language_codes"][0]

        for page in yaml_dict["menu"]["pages"]:
            if page.get("sections"):
                for section in page["sections"]:
                    # Inject combined section name (all langs) for rendering TOC
                    section_name_components = []
                    for k in section.keys():
                        if k.startswith("name_"):
                            section_name_components.append(section[k])
                    if section_name_components:
                        section["_id"] = _slugify(
                            section.get("name_" + primary_lang, "")
                        )
                        section["_name_all_langs"] = " / ".join(section_name_components)

                    if section.get("menu_items"):
                        # Inject data from known_dishes into menu YAML
                        for menu_item in section["menu_items"]:
                            lang = "name_" + primary_lang
                            if menu_item.get(lang):
                                primary_name = menu_item[lang]
                                if known_dish_lookuptable.get(primary_name):
                                    known_dish = known_dish_lookuptable[primary_name]
                                    for k, v in known_dish.items():
                                        if k not in menu_item:
                                            menu_item[k] = v

    display_language_codes = []
    if yaml_dict.get("menu"):
        display_language_codes = yaml_dict["menu"]["language_codes"]
        if "en" not in display_language_codes:
            display_language_codes.append("en")

    ordered_known_terms = sorted(known_terms_lookup_dict, key=len, reverse=True)

    # CHINESE ONLY
    # Gather all primary dish names from YAML
    chinese_dish_name_to_menu_item = {}
    if yaml_dict.get("menu"):
        primary_lang_tag = yaml_dict["menu"]["language_codes"][0]
        primary_lang_code = primary_lang_tag.split("-")[0]

        for page in yaml_dict["menu"]["pages"]:
            sections = page.get("sections", [])
            for section in sections:
                menu_items = section.get("menu_items", [])
                for menu_item in menu_items:
                    primary_name = menu_item.get("name_" + primary_lang_tag)
                    if primary_name and primary_lang_code == "zh":
                        chinese_dish_name_to_menu_item[primary_name] = menu_item

    # CHINESE ONLY
    # For each Chinese name, match against known_terms to try to annotate it
    dish_name_to_annotated_html = {}
    for dish_name in chinese_dish_name_to_menu_item.keys():
        annotated_html = ""
        i = 0
        while i < len(dish_name):
            matched = False

            # Check for the longest possible match first
            for key in ordered_known_terms:
                if dish_name[i:].startswith(key):
                    annotated_html += (
                        '<span class="dish-term-native">'
                        f"{key}"
                        f'<span class="dish-term-translated">'
                    )
                    wikipedia_url = known_terms_lookup_dict[key]["wikipedia_url"]
                    if wikipedia_url:
                        annotated_html += f'<a href="{wikipedia_url}" target="wikipedia" rel="noopener">'
                    annotated_html += f"{known_terms_lookup_dict[key]['en']}"
                    if wikipedia_url:
                        annotated_html += f"</a>"
                    annotated_html += "</span>"
                    annotated_html += "</span>"

                    i += len(key)
                    matched = True

                    # Use data from this matching term to possibly enrich the menu_item dict
                    menu_item = chinese_dish_name_to_menu_item[dish_name]
                    known_term = known_terms_lookup_dict[key]
                    if not menu_item.get("image_url") and known_term.get("image_url"):
                        menu_item["image_url"] = known_term["image_url"]
                    if not menu_item.get("wikipedia_url") and known_term.get(
                        "wikipedia_url"
                    ):
                        menu_item["wikipedia_url"] = known_term["wikipedia_url"]

                    break

            # If no match, just add the character
            if not matched:
                annotated_html += (
                    '<span class="dish-term-native">' f"{dish_name[i]}" "</span>"
                )
                i += 1
        dish_name_to_annotated_html[dish_name] = annotated_html

    env = Environment(loader=FileSystemLoader("."))
    # https://jinja.palletsprojects.com/en/3.1.x/templates/#whitespace-control
    env.trim_blocks = True
    env.lstrip_blocks = True

    for filter_name in jinja_filters.ALL_FILTERS:
        env.filters[filter_name] = getattr(jinja_filters, filter_name)

    template = env.get_template("templates/menu_template.j2")
    rendered_html = template.render(
        data=yaml_dict,
        display_language_codes=display_language_codes,
        dish_name_to_annotated_html=dish_name_to_annotated_html,
    )

    with open(output_html_path, "w", encoding="utf-8") as html_path:
        html_path.write(rendered_html)

    return yaml_dict


def process_menu_yaml_paths(
    input_dir: str,
    output_dir: str,
    known_dish_lookuptable: dict[str, dict[str, Any]],
    known_terms_lookup_dict: dict[str, Any],
) -> dict[str, Any]:
    menu_filename_to_menu_yaml_dicts = {}
    for root, _, files in os.walk(input_dir):
        for filename in files:
            if filename.endswith(".yaml"):
                input_path = os.path.join(root, filename)

                relative_path = os.path.relpath(input_path, input_dir)
                output_filename = os.path.splitext(relative_path)[0] + ".html"
                output_path = os.path.join(output_dir, output_filename)

                yaml_dict = generate_menu_html(
                    input_path,
                    output_path,
                    known_dish_lookuptable,
                    known_terms_lookup_dict,
                )

                yaml_dict["_output_filename"] = output_filename
                menu_filename_to_menu_yaml_dicts[output_filename] = yaml_dict

                print(f"Processed: {input_path} -> {output_path}")

    return menu_filename_to_menu_yaml_dicts


def generate_index_html(
    menu_yaml_dicts: list[dict[str, Any]],
    known_dishes: list[dict[str, Any]],
    output_html_path: str,
) -> None:
    env = Environment(loader=FileSystemLoader("."))
    # https://jinja.palletsprojects.com/en/3.1.x/templates/#whitespace-control
    env.trim_blocks = True
    env.lstrip_blocks = True

    template = env.get_template("templates/index_template.j2")
    rendered_html = template.render(
        menu_yaml_dicts=menu_yaml_dicts, known_dishes=known_dishes
    )

    with open(output_html_path, "w", encoding="utf-8") as html_path:
        html_path.write(rendered_html)


def generate_dishes_html(
    known_locale_lookuptable: dict[str, dict[str, Any]],
    known_dishes: list[dict[str, Any]],
    menu_filename_to_menu_yaml_dicts: dict[str, dict[str, Any]],
    output_html_path: str,
) -> None:
    # Build mapping of dish names to menu_filename
    dish_name_to_menu_filename = {}
    for yaml_dict in menu_filename_to_menu_yaml_dicts.values():
        if yaml_dict.get("menu"):
            menu = yaml_dict["menu"]
            language_codes = menu["language_codes"]
            for page in menu["pages"]:
                if page.get("sections"):
                    for section in page["sections"]:
                        if section.get("menu_items"):
                            for menu_item in section["menu_items"]:
                                for language_code in language_codes:
                                    name_lang = "name_" + language_code
                                    if menu_item.get(name_lang):
                                        name = menu_item[name_lang]
                                        if not dish_name_to_menu_filename.get(name):
                                            dish_name_to_menu_filename[name] = []
                                        dish_name_to_menu_filename[name].append(
                                            yaml_dict["_output_filename"]
                                        )

    # Inject into known_dishes
    for known_dish in known_dishes:
        menu_filename_set = set()
        for dish_name in known_dish["name_native"].split(","):
            menu_filenames = dish_name_to_menu_filename.get(dish_name)
            if menu_filenames:
                menu_filename_set.update(menu_filenames)
        known_dish["_menu_filenames"] = list(menu_filename_set)

    # Group all dishes by locale
    locale_dish_groups = []
    for locale_dict in known_locale_lookuptable.values():
        locale_code = locale_dict["locale_code"]
        locale_dishes = [
            dish for dish in known_dishes if dish["locale_code"] == locale_code
        ]
        locale_dishes = sorted(locale_dishes, key=lambda d: d["name_en"])
        locale_dish_group = {**locale_dict, "dishes": locale_dishes}
        locale_dish_groups.append(locale_dish_group)

    env = Environment(loader=FileSystemLoader("."))
    # https://jinja.palletsprojects.com/en/3.1.x/templates/#whitespace-control
    env.trim_blocks = True
    env.lstrip_blocks = True

    template = env.get_template("templates/dishes_template.j2")
    rendered_html = template.render(
        locale_dish_groups=locale_dish_groups,
        menu_filename_to_menu_yaml_dicts=menu_filename_to_menu_yaml_dicts,
    )

    with open(output_html_path, "w", encoding="utf-8") as html_path:
        html_path.write(rendered_html)


def _gather_stats(
    menu_yaml_dicts: list[dict[str, Any]],
    known_dish_lookuptable: dict[str, dict[str, Any]],
    known_terms_lookup_dict: dict[str, Any],
) -> dict[str, Any]:
    # Find dish names
    primary_names = []
    for yaml_dict in menu_yaml_dicts:
        if yaml_dict.get("menu"):
            menu = yaml_dict["menu"]
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
            primary_names.extend(menu_primary_name_set)

    # Find common dishes
    name_counter = collections.Counter(primary_names)
    filtered_c = {k: v for k, v in name_counter.items() if v >= 3}
    common_dishes = [
        (k, v, known_dish_lookuptable.get(k, {}).get("name_en", "❓"))
        for k, v in sorted(filtered_c.items(), key=lambda x: x[1], reverse=True)
    ]

    # Data linting
    for dish_name in filtered_c:
        if not dish_name in known_dish_lookuptable.keys():
            print(
                f"WARNING: {dish_name} (count {name_counter[dish_name]}) is not in known_dishes"
            )

    # Find top characters
    character_counter = collections.Counter()
    for primary_name in primary_names:
        character_counter.update(primary_name)
    unique_character_count = len(character_counter)

    top_characters = character_counter.most_common(100)
    top_characters = [
        (k, v, known_terms_lookup_dict.get(k, {}).get("en", "❓"))
        for k, v in top_characters
    ]

    top_chars_not_known = []
    for tuple in top_characters:
        if (
            tuple[0] not in "".join(known_terms_lookup_dict.keys())
            and tuple[0].isalpha()
        ):
            top_chars_not_known.append(tuple[0])
    if top_chars_not_known:
        print(f"Top characters not present in known_terms: {top_chars_not_known}")

    # Find top n-grams
    unique_primary_names = list(set(primary_names))
    top_3gram_tuples = []
    for k, v in find_top_ngrams(unique_primary_names, 3, 100):
        if v >= 3:
            en = known_terms_lookup_dict.get(k, {}).get("en")
            if en:
                en = f'"{en}"'
            else:
                en = " + ".join(
                    [
                        f'"{known_terms_lookup_dict.get(c, {}).get("en", "❓")}"'
                        for c in k
                    ]
                )
            t = (k, v, en)
            top_3gram_tuples.append(t)

    top_3grams = [t[0] for t in top_3gram_tuples]

    top_2gram_tuples = []
    for k, v in find_top_ngrams(unique_primary_names, 2, 100):
        if v >= 3:
            en = known_terms_lookup_dict.get(k, {}).get("en")
            if en:
                en = f'"{en}"'
            else:
                en = " + ".join(
                    [
                        f'"{known_terms_lookup_dict.get(c, {}).get("en", "❓")}"'
                        for c in k
                    ]
                )
            t = (k, v, en)

            # Filter out 2-grams e.g. "黃毛" that are included in 3-grams e.g. "黃毛雞"
            is_included = False
            for three_gram in top_3grams:
                if k in three_gram:
                    is_included = True
                    break

            if not is_included:
                top_2gram_tuples.append(t)

    return {
        "menu_count": len(menu_yaml_dicts),
        "unique_dish_count": len(set(primary_names)),
        "common_dishes": common_dishes,
        "unique_character_count": unique_character_count,
        "top_characters": top_characters,
        "top_2grams": top_2gram_tuples,
        "top_3grams": top_3gram_tuples,
    }


def generate_stats_html(
    menu_yaml_dicts: list[dict[str, Any]],
    known_dish_lookuptable: dict[str, dict[str, Any]],
    known_terms_lookup_dict: dict[str, dict[str, Any]],
    output_html_path: str,
) -> None:
    stats = _gather_stats(
        list(menu_yaml_dicts), known_dish_lookuptable, known_terms_lookup_dict
    )

    env = Environment(loader=FileSystemLoader("."))
    # https://jinja.palletsprojects.com/en/3.1.x/templates/#whitespace-control
    env.trim_blocks = True
    env.lstrip_blocks = True

    template = env.get_template("templates/stats_template.j2")
    rendered_html = template.render(stats=stats)

    with open(output_html_path, "w", encoding="utf-8") as html_path:
        html_path.write(rendered_html)


def main(input_dir: str, output_dir: str):
    # Load canned data
    known_locale_lookuptable = load_known_locales()
    known_terms_lookup_dict, known_dishes = load_known_terms()

    # Map known_dish's name_native to known_dish dict
    known_dish_lookuptable = {}
    for known_dish in known_dishes:
        name_native_commaseparated = known_dish["name_native"].split(",")
        d = known_dish.copy()
        d.pop("name_native")
        for native_name in name_native_commaseparated:
            known_dish_lookuptable[native_name] = d

    prepare_output_dir(output_dir)

    # Generate menu pages
    menu_filename_to_menu_yaml_dicts = process_menu_yaml_paths(
        input_dir, output_dir, known_dish_lookuptable, known_terms_lookup_dict
    )

    # Generate index page
    output_path = os.path.join(output_dir, "index.html")
    generate_index_html(
        list(menu_filename_to_menu_yaml_dicts.values()), known_dishes, output_path
    )
    print(f"Processed: {output_path}")

    # Generate dishes page
    output_path = os.path.join(output_dir, "dishes.html")
    generate_dishes_html(
        known_locale_lookuptable,
        known_dishes,
        menu_filename_to_menu_yaml_dicts,
        output_path,
    )
    print(f"Processed: {output_path}")

    # Generate stats page
    output_path = os.path.join(output_dir, "stats.html")
    generate_stats_html(
        list(menu_filename_to_menu_yaml_dicts.values()),
        known_dish_lookuptable,
        known_terms_lookup_dict,
        output_path,
    )
    print(f"Processed: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) > 4:
        print("Usage: python main.py [input_dir] [output_dir]")
        sys.exit(1)

    input_dir = sys.argv[1] if len(sys.argv) >= 2 else INPUT_DIR
    output_dir = sys.argv[2] if len(sys.argv) >= 3 else OUTPUT_DIR

    main(input_dir, output_dir)
