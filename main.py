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
from model import KnownTerm
from schema import RESTAURANT_SCHEMA
from stats import gather_menu_stats

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


def load_known_locales() -> dict[str, dict[str, str]]:
    known_locales = []
    with open("data/known_locales.tsv", "r", encoding="utf-8") as csvfile:
        csvreader = csv.DictReader(csvfile, delimiter="\t")
        for row in csvreader:
            assert any(row.values()), "ERROR: known_locales has empty lines"
            known_locales.append(row)

    # Map locale_code to locale dict
    known_dish_lookup_dict = {}
    for known_locale in known_locales:
        locale_code = known_locale["locale_code"]
        known_dish_lookup_dict[locale_code] = known_locale
    return known_dish_lookup_dict


def load_known_terms() -> tuple[list[KnownTerm], dict[str, KnownTerm], list[KnownTerm]]:
    known_terms = []
    with open("data/known_terms.tsv", "r", encoding="utf-8") as csvfile:
        csvreader = csv.DictReader(csvfile, delimiter="\t")
        for row in csvreader:
            assert any(row.values()), "ERROR: known_terms has empty lines"

            known_term = KnownTerm(row)
            known_terms.append(known_term)

    known_terms_lookup_dict = {}
    # Use all native names as lookup keys
    for known_term in known_terms:
        known_terms_lookup_dict.update(
            {native_name: known_term for native_name in known_term.all_native_names}
        )

    known_dishes = []
    for known_term in known_terms:
        if known_term.dish_cuisine_locale:
            known_dishes.append(known_term)

    return known_terms, known_terms_lookup_dict, known_dishes


def _slugify(s: str) -> str:
    return "".join([c if c.isalnum() else "-" for c in s])


def generate_menu_html(
    input_yaml_path: str,
    output_filename: str,
    output_html_path: str,
    known_dish_lookup_dict: dict[str, KnownTerm],
    known_terms_lookup_dict: dict[str, KnownTerm],
) -> dict[str, Any]:
    with open(input_yaml_path, "r", encoding="utf-8") as yaml_path:
        yaml_data = strictyaml.load(yaml_path.read(), RESTAURANT_SCHEMA)

    # The type checker thinks yaml_data.data is a str, not a dict
    yaml_dict = typing.cast(OrderedDict[str, Any], yaml_data.data)

    yaml_dict["_output_filename"] = output_filename

    # Inject _date_modified into the YAML data
    mod_date = datetime.datetime.fromtimestamp(os.path.getmtime(input_yaml_path))
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
                                known_dish = known_dish_lookup_dict.get(primary_name)
                                if known_dish:
                                    for k in [
                                        "wikipedia_url",
                                        "image_url",
                                        "description_en",
                                    ]:
                                        v = getattr(known_dish, k)
                                        if v and k not in menu_item:
                                            menu_item[k] = v

    # Display languages are all languages in the menu, plus English
    display_language_codes = []
    if yaml_dict.get("menu"):
        display_language_codes = yaml_dict["menu"]["language_codes"]
        if "en" not in display_language_codes:
            display_language_codes.append("en")

    # CHINESE ONLY
    def _annotate_menu_section_or_item_with_known_terms(
        section_or_item: dict[str, Any],
        is_section: bool,
        ordered_known_terms: list[str],
        known_terms_lookup_dict: dict[str, KnownTerm],
    ) -> list[KnownTerm]:
        primary_lang_tag = yaml_dict["menu"]["language_codes"][0]

        primary_lang_code = primary_lang_tag.split("-")[0]
        if not primary_lang_code == "zh":
            return []

        primary_name = section_or_item.get("name_" + primary_lang_tag)
        if not primary_name:
            return []

        matched_known_terms = []
        annotated_html = ""
        # Match from left to right
        i = 0
        while i < len(primary_name):
            matched = False

            # Preferring longest possible match first
            for key in ordered_known_terms:
                assert len(key) > 0

                if primary_name[i:].startswith(key):
                    annotated_html += '<span class="term-native">'
                    annotated_html += key
                    annotated_html += '<span class="term-translated">'

                    known_term = known_terms_lookup_dict[key]

                    wikipedia_url = known_term.wikipedia_url
                    if wikipedia_url:
                        annotated_html += f'<a href="{wikipedia_url}" target="wikipedia" rel="noopener">'

                    term_en = known_term.name_en
                    if is_section:
                        term_en = term_en.title()
                    annotated_html += term_en

                    if wikipedia_url:
                        annotated_html += f"</a>"

                    annotated_html += "</span>"
                    annotated_html += "</span>"

                    i += len(key)
                    matched = True
                    matched_known_terms.append(known_term)

                    # Use data from this matching term to possibly enrich the section_or_item
                    if not section_or_item.get("image_url") and known_term.image_url:
                        section_or_item["image_url"] = known_term.image_url
                    if (
                        not section_or_item.get("wikipedia_url")
                        and known_term.wikipedia_url
                    ):
                        section_or_item["wikipedia_url"] = known_term.wikipedia_url

                    break

            # If no match, just add the character
            if not matched:
                annotated_html += (
                    '<span class="term-native">' f"{primary_name[i]}" "</span>"
                )
                i += 1

        section_or_item["_annotated_name"] = annotated_html
        return matched_known_terms

    # CHINESE ONLY
    # Match against longest terms first
    ordered_nondish_terms = sorted(
        {k: v for k, v in known_terms_lookup_dict.items() if not v.dish_cuisine_locale},
        key=len,
        reverse=True,
    )
    ordered_all_terms = sorted(known_terms_lookup_dict, key=len, reverse=True)

    # For each Chinese section/menu_item, try to annotate it
    menu = yaml_dict.get("menu")
    if menu:
        for page in menu["pages"]:
            sections = page.get("sections", [])
            for section in sections:
                # Annotate section name
                _annotate_menu_section_or_item_with_known_terms(
                    section, True, ordered_nondish_terms, known_terms_lookup_dict
                )

                menu_items = section.get("menu_items", [])
                for menu_item in menu_items:
                    matched_known_terms = (
                        _annotate_menu_section_or_item_with_known_terms(
                            menu_item, False, ordered_all_terms, known_terms_lookup_dict
                        )
                    )
                    for known_term in matched_known_terms:
                        if not output_filename in known_term._menu_filenames:
                            known_term._menu_filenames.append(output_filename)

    env = Environment(loader=FileSystemLoader("templates"))
    # https://jinja.palletsprojects.com/en/3.1.x/templates/#whitespace-control
    env.trim_blocks = True
    env.lstrip_blocks = True

    # Install custom Jinja filters
    for filter_name in jinja_filters.ALL_FILTERS:
        env.filters[filter_name] = getattr(jinja_filters, filter_name)

    # Render the output file
    template = env.get_template("menu_template.j2")
    rendered_html = template.render(
        data=yaml_dict, display_language_codes=display_language_codes
    )

    with open(output_html_path, "w", encoding="utf-8") as html_path:
        html_path.write(rendered_html)

    return yaml_dict


def process_menu_yaml_paths(
    input_dir: str,
    output_dir: str,
    known_dish_lookup_dict: dict[str, KnownTerm],
    known_terms_lookup_dict: dict[str, KnownTerm],
) -> dict[str, Any]:
    menu_filename_to_menu_yaml_dict = {}
    for root, _, files in os.walk(input_dir):
        for filename in files:
            if filename.endswith(".yaml"):
                input_path = os.path.join(root, filename)

                relative_path = os.path.relpath(input_path, input_dir)
                output_filename = os.path.splitext(relative_path)[0] + ".html"
                output_path = os.path.join(output_dir, output_filename)

                yaml_dict = generate_menu_html(
                    input_path,
                    output_filename,
                    output_path,
                    known_dish_lookup_dict,
                    known_terms_lookup_dict,
                )

                menu_filename_to_menu_yaml_dict[output_filename] = yaml_dict

                print(f"Processed: {input_path} -> {output_path}")

    return menu_filename_to_menu_yaml_dict


def generate_index_html(
    menu_yaml_dicts: list[dict[str, Any]],
    known_dishes: list[KnownTerm],
    output_html_path: str,
) -> None:
    env = Environment(loader=FileSystemLoader("templates"))
    # https://jinja.palletsprojects.com/en/3.1.x/templates/#whitespace-control
    env.trim_blocks = True
    env.lstrip_blocks = True

    # Render the output file
    template = env.get_template("index_template.j2")
    rendered_html = template.render(
        menu_yaml_dicts=menu_yaml_dicts, known_dishes=known_dishes
    )

    with open(output_html_path, "w", encoding="utf-8") as html_path:
        html_path.write(rendered_html)


def generate_dishes_html(
    known_locale_lookup_dict: dict[str, dict[str, str]],
    known_dishes: list[KnownTerm],
    menu_filename_to_menu_yaml_dict: dict[str, dict[str, Any]],
    output_html_path: str,
) -> None:
    # Group known_dishes by locale
    locale_dish_groups = []
    for locale_dict in known_locale_lookup_dict.values():
        locale_code: str = locale_dict["locale_code"]
        locale_dishes = [
            dish for dish in known_dishes if dish.dish_cuisine_locale == locale_code
        ]
        locale_dishes = sorted(locale_dishes, key=lambda d: d.name_en)
        locale_dish_group = {**locale_dict, "dishes": locale_dishes}
        locale_dish_groups.append(locale_dish_group)
    locale_dish_groups = sorted(locale_dish_groups, key=lambda d: d["cuisine_name_en"])

    env = Environment(loader=FileSystemLoader("templates"))
    # https://jinja.palletsprojects.com/en/3.1.x/templates/#whitespace-control
    env.trim_blocks = True
    env.lstrip_blocks = True

    # Render the output file
    template = env.get_template("dishes_template.j2")
    rendered_html = template.render(
        locale_dish_groups=locale_dish_groups,
        menu_filename_to_menu_yaml_dict=menu_filename_to_menu_yaml_dict,
    )

    with open(output_html_path, "w", encoding="utf-8") as html_path:
        html_path.write(rendered_html)


def generate_stats_html(
    menu_yaml_dicts: list[dict[str, Any]],
    known_terms_lookup_dict: dict[str, KnownTerm],
    known_dishes: list[KnownTerm],
    known_dish_lookup_dict: dict[str, KnownTerm],
    output_html_path: str,
) -> None:
    menu_stats = gather_menu_stats(
        menu_yaml_dicts, known_terms_lookup_dict, known_dish_lookup_dict
    )

    env = Environment(loader=FileSystemLoader("templates"))
    # https://jinja.palletsprojects.com/en/3.1.x/templates/#whitespace-control
    env.trim_blocks = True
    env.lstrip_blocks = True

    # Render the output file
    template = env.get_template("stats_template.j2")
    rendered_html = template.render(
        menu_stats=menu_stats,
        known_dishes=known_dishes,
        known_terms_lookup_dict=known_terms_lookup_dict,
        known_dish_lookup_dict=known_dish_lookup_dict,
    )

    with open(output_html_path, "w", encoding="utf-8") as html_path:
        html_path.write(rendered_html)


def main(input_dir: str, output_dir: str):
    # Load canned data
    known_locale_lookup_dict = load_known_locales()
    known_terms, known_terms_lookup_dict, known_dishes = load_known_terms()

    # Use all native names as lookup keys
    known_dish_lookup_dict = {}
    for known_dish in known_dishes:
        known_dish_lookup_dict.update(
            {native_name: known_dish for native_name in known_dish.all_native_names}
        )

    prepare_output_dir(output_dir)

    # Generate menu pages
    menu_filename_to_menu_yaml_dict = process_menu_yaml_paths(
        input_dir, output_dir, known_dish_lookup_dict, known_terms_lookup_dict
    )

    # Generate index page
    output_path = os.path.join(output_dir, "index.html")
    generate_index_html(
        list(menu_filename_to_menu_yaml_dict.values()), known_dishes, output_path
    )
    print(f"Processed: {output_path}")

    # Generate dishes page
    output_path = os.path.join(output_dir, "dishes.html")
    generate_dishes_html(
        known_locale_lookup_dict,
        known_dishes,
        menu_filename_to_menu_yaml_dict,
        output_path,
    )
    print(f"Processed: {output_path}")

    # Generate stats page
    output_path = os.path.join(output_dir, "stats.html")
    generate_stats_html(
        list(menu_filename_to_menu_yaml_dict.values()),
        known_terms_lookup_dict,
        known_dishes,
        known_dish_lookup_dict,
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
