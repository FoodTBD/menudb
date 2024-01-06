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


def load_known_dishes() -> dict[str, Any]:
    known_dishes = {}
    with open("known_dishes.tsv", "r", encoding="utf-8") as csvfile:
        csvreader = csv.DictReader(csvfile, delimiter="\t")
        for row in csvreader:
            name_native_commaseparated = row["name_native"].split(",")
            row.pop("name_native")
            for native_name in name_native_commaseparated:
                known_dishes[native_name] = row
    return known_dishes


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


def generate_index_html(yaml_dicts: list[str], output_html_path: str) -> None:
    env = Environment(loader=FileSystemLoader("."))

    # https://jinja.palletsprojects.com/en/3.1.x/templates/#whitespace-control
    env.trim_blocks = True
    env.lstrip_blocks = True

    for filter_name in jinja_filters.ALL_FILTERS:
        env.filters[filter_name] = getattr(jinja_filters, filter_name)

    template = env.get_template("templates/index_template.j2")
    rendered_html = template.render(data=yaml_dicts)

    with open(output_html_path, "w", encoding="utf-8") as html_path:
        html_path.write(rendered_html)


def process_yaml_paths(
    input_dir: str, output_dir: str, known_dishes: dict[str, Any]
) -> list[dict[str, Any]]:
    yaml_dicts = []
    for root, _, files in os.walk(input_dir):
        for filename in files:
            if filename.endswith(".yaml"):
                input_path = os.path.join(root, filename)
                relative_path = os.path.relpath(input_path, input_dir)
                output_filename = os.path.splitext(relative_path)[0] + ".html"
                output_path = os.path.join(output_dir, output_filename)

                yaml_dict = generate_menu_html(input_path, output_path, known_dishes)
                yaml_dict["_output_filename"] = output_filename
                yaml_dicts.append(yaml_dict)

                print(f"Processed: {input_path} -> {output_path}")

    output_path = os.path.join(output_dir, "index.html")
    generate_index_html(yaml_dicts, output_path)
    print(f"Processed: {output_path}")

    return yaml_dicts


def print_stats(yaml_dicts: list[dict[str, Any]]) -> None:
    print(f"Menus: {len(yaml_dicts)}")

    primary_names = []
    for yaml_dict in yaml_dicts:
        if yaml_dict.get("menu"):
            menu = yaml_dict["menu"]
            primary_lang = menu["language_codes"][0]
            for page in menu["pages"]:
                if page.get("sections"):
                    for section in page["sections"]:
                        for menu_item in section["menu_items"]:
                            lang = "name_" + primary_lang
                            if menu_item.get(lang):
                                primary_name = menu_item[lang]
                                primary_names.append(primary_name)

    print("Unique dish names: " + str(len(set(primary_names))))

    name_counter = collections.Counter(primary_names)
    filtered_c = {k: v for k, v in name_counter.items() if v > 1}
    print(
        f"Common dishes ({len(filtered_c)} count): {sorted(filtered_c.items(), key=lambda x: x[1], reverse=True)}"
    )

    character_counter = collections.Counter()
    for primary_name in primary_names:
        character_counter.update(primary_name)
    print("Unique characters: " + str(len(character_counter)))
    print("Top 10 characters: " + str(character_counter.most_common(10)))

    for dish_name in filtered_c:
        if not dish_name in known_dishes:
            print(
                f"Warning: {dish_name} (count {name_counter[dish_name]}) is not in database of known dishes"
            )


if __name__ == "__main__":
    if len(sys.argv) > 4:
        print("Usage: python main.py [input_dir] [output_dir]")
        sys.exit(1)

    input_dir = sys.argv[1] if len(sys.argv) >= 2 else INPUT_DIR
    output_dir = sys.argv[2] if len(sys.argv) >= 3 else OUTPUT_DIR

    prepare_output_dir(output_dir)
    known_dishes = load_known_dishes()
    yaml_dicts = process_yaml_paths(input_dir, output_dir, known_dishes)
    print_stats(yaml_dicts)
