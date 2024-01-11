import collections
import csv
import datetime
import os
import re
import shutil
import sys
import typing
import urllib.parse
from typing import Any, OrderedDict

import strictyaml
from jinja2 import Environment, FileSystemLoader

import jinja_filters
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


def load_known_dishes() -> list[dict[str, Any]]:
    known_dishes = []
    with open("data/known_dishes.tsv", "r", encoding="utf-8") as csvfile:
        csvreader = csv.DictReader(csvfile, delimiter="\t")
        for row in csvreader:
            assert any(row.values()), "ERROR: known_dishes has empty lines"

            # Check all Wikimedia image references and rewrite them to be downscaled to 128px
            image_url = row["image_url"]
            o = urllib.parse.urlparse(image_url)
            if o.path:
                assert (
                    o.hostname
                ), f'ERROR: known_dishes has invalid image_url "{image_url}"'

            if o.hostname:
                if o.hostname.endswith("wikimedia.org") or o.hostname.endswith(
                    "wikipedia.org"
                ):
                    m = re.match(
                        r"https://upload\.wikimedia\.org/wikipedia/commons/thumb/(.+)/(.+)/(.+)/(\d+)px-(.+)",
                        image_url,
                    )
                    assert (
                        m
                    ), f'ERROR: known_dishes has non-standard Wikipedia image_url "{image_url}". See README.md'

                    image_url = image_url.replace(f"/{m.group(4)}px-", "/128px-")
                    row["image_url"] = image_url

            known_dishes.append(row)
    return known_dishes


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


def generate_menu_html(
    input_yaml_path: str, output_html_path: str, known_dishes: dict[str, Any]
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

    # Inject data from known_dishes.csv into menu.pages[*].sections[*].menu_items[*]
    if yaml_dict.get("menu"):
        primary_lang = yaml_dict["menu"]["language_codes"][0]
        for page in yaml_dict["menu"]["pages"]:
            if page.get("sections"):
                for section in page["sections"]:
                    if section.get("menu_items"):
                        for menu_item in section["menu_items"]:
                            lang = "name_" + primary_lang
                            if menu_item.get(lang):
                                primary_name = menu_item[lang]
                                if known_dishes.get(primary_name):
                                    known_dish = known_dishes[primary_name]
                                    for k, v in known_dish.items():
                                        if k not in menu_item:
                                            menu_item[k] = v
                                        # else:
                                        #     print(
                                        #         f"{input_yaml_path}: Not overwriting {k} for {primary_name}"
                                        #     )

    language_codes = []
    if yaml_dict.get("menu"):
        language_codes = yaml_dict["menu"]["language_codes"]
        if "en" not in language_codes:
            language_codes.append("en")

    env = Environment(loader=FileSystemLoader("."))

    # https://jinja.palletsprojects.com/en/3.1.x/templates/#whitespace-control
    env.trim_blocks = True
    env.lstrip_blocks = True

    for filter_name in jinja_filters.ALL_FILTERS:
        env.filters[filter_name] = getattr(jinja_filters, filter_name)

    template = env.get_template("templates/menu_template.j2")
    rendered_html = template.render(data=yaml_dict, language_codes=language_codes)

    with open(output_html_path, "w", encoding="utf-8") as html_path:
        html_path.write(rendered_html)

    return yaml_dict


def process_menu_yaml_paths(input_dir: str, output_dir: str) -> dict[str, Any]:
    # Generate name_native to known_dish dict mapping
    known_dish_lookuptable = {}
    for known_dish in known_dishes:
        name_native_commaseparated = known_dish["name_native"].split(",")
        d = known_dish.copy()
        d.pop("name_native")
        for native_name in name_native_commaseparated:
            known_dish_lookuptable[native_name] = d

    menu_filename_to_menu_yaml_dicts = {}
    for root, _, files in os.walk(input_dir):
        for filename in files:
            if filename.endswith(".yaml"):
                input_path = os.path.join(root, filename)

                relative_path = os.path.relpath(input_path, input_dir)
                output_filename = os.path.splitext(relative_path)[0] + ".html"
                output_path = os.path.join(output_dir, output_filename)

                yaml_dict = generate_menu_html(
                    input_path, output_path, known_dish_lookuptable
                )

                yaml_dict["_output_filename"] = output_filename
                menu_filename_to_menu_yaml_dicts[output_filename] = yaml_dict

                print(f"Processed: {input_path} -> {output_path}")

    print_stats(list(menu_filename_to_menu_yaml_dicts.values()), known_dish_lookuptable)

    return menu_filename_to_menu_yaml_dicts


def print_stats(
    menu_yaml_dicts: list[dict[str, Any]], known_dish_lookuptable: dict[str, Any]
) -> None:
    eatsdb_names_set = set(load_eatsdb_names())

    print()
    print(f"Total menu count: {len(menu_yaml_dicts)}")

    # Build list of primary_names and image_names
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

    print("Unique dish names: " + str(len(set(primary_names))))

    name_counter = collections.Counter(primary_names)
    filtered_c = {k: v for k, v in name_counter.items() if v > 1}
    print(
        f"Common dishes ({len(filtered_c)}): {sorted(filtered_c.items(), key=lambda x: x[1], reverse=True)}"
    )

    character_counter = collections.Counter()
    for primary_name in primary_names:
        character_counter.update(primary_name)
    print("Unique characters: " + str(len(character_counter)))
    print("Top 10 characters: " + str(character_counter.most_common(10)))

    # Data linting
    for dish_name in filtered_c:
        if not dish_name in known_dish_lookuptable:
            print(
                f"WARNING: {dish_name} (count {name_counter[dish_name]}) is not in known_dishes"
            )
    for dish_name in primary_names:
        if not dish_name in known_dish_lookuptable and dish_name in eatsdb_names_set:
            print(
                f"WARNING: {dish_name} (count {name_counter[dish_name]}) is not in known_dishes but is in EatsDB"
            )


def generate_index_html(
    menu_yaml_dicts: list[dict[str, Any]], output_html_path: str
) -> None:
    env = Environment(loader=FileSystemLoader("."))

    # https://jinja.palletsprojects.com/en/3.1.x/templates/#whitespace-control
    env.trim_blocks = True
    env.lstrip_blocks = True

    for filter_name in jinja_filters.ALL_FILTERS:
        env.filters[filter_name] = getattr(jinja_filters, filter_name)

    template = env.get_template("templates/index_template.j2")
    rendered_html = template.render(data=menu_yaml_dicts)

    with open(output_html_path, "w", encoding="utf-8") as html_path:
        html_path.write(rendered_html)


def generate_dishes_html(
    known_dishes: list[dict[str, Any]],
    menu_filename_to_menu_yaml_dicts: dict[str, Any],
    output_html_path: str,
) -> None:
    all_dishes = sorted(known_dishes, key=lambda d: d["name_en"])

    # Build mapping of primary_name to menu_filename
    dish_name_to_menu_filename = {}
    for yaml_dict in menu_filename_to_menu_yaml_dicts.values():
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
            for primary_name in menu_primary_name_set:
                if not dish_name_to_menu_filename.get(primary_name):
                    dish_name_to_menu_filename[primary_name] = []
                dish_name_to_menu_filename[primary_name].append(
                    yaml_dict["_output_filename"]
                )

    env = Environment(loader=FileSystemLoader("."))

    # https://jinja.palletsprojects.com/en/3.1.x/templates/#whitespace-control
    env.trim_blocks = True
    env.lstrip_blocks = True

    for filter_name in jinja_filters.ALL_FILTERS:
        env.filters[filter_name] = getattr(jinja_filters, filter_name)

    template = env.get_template("templates/dishes_template.j2")
    rendered_html = template.render(
        all_dishes=all_dishes,
        dish_name_to_menu_filename=dish_name_to_menu_filename,
        menu_filename_to_menu_yaml_dicts=menu_filename_to_menu_yaml_dicts,
    )

    with open(output_html_path, "w", encoding="utf-8") as html_path:
        html_path.write(rendered_html)


if __name__ == "__main__":
    if len(sys.argv) > 4:
        print("Usage: python main.py [input_dir] [output_dir]")
        sys.exit(1)

    input_dir = sys.argv[1] if len(sys.argv) >= 2 else INPUT_DIR
    output_dir = sys.argv[2] if len(sys.argv) >= 3 else OUTPUT_DIR

    prepare_output_dir(output_dir)

    known_dishes = load_known_dishes()

    menu_filename_to_menu_yaml_dicts = process_menu_yaml_paths(input_dir, output_dir)

    output_path = os.path.join(output_dir, "index.html")
    generate_index_html(list(menu_filename_to_menu_yaml_dicts.values()), output_path)
    print(f"Processed: {output_path}")

    output_path = os.path.join(output_dir, "dishes.html")
    generate_dishes_html(known_dishes, menu_filename_to_menu_yaml_dicts, output_path)
    print(f"Processed: {output_path}")
