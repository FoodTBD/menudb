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

STATIC_DIR = "static"
INPUT_DIR = "content"
OUTPUT_DIR = "output"


def generate_menu_html(input_yaml_path: str, output_html_path: str) -> dict[str, Any]:
    with open(input_yaml_path, "r", encoding="utf-8") as yaml_path:
        yaml_data = strictyaml.load(yaml_path.read(), label="!yaml")

    # Inject the modification date into the YAML data
    mod_date = datetime.datetime.fromtimestamp(os.path.getmtime(input_yaml_path))
    # The type checker thinks yaml_data.data is a str, not a dict
    yaml_dict = typing.cast(OrderedDict[str, Any], yaml_data.data)
    yaml_dict["_date_modified"] = mod_date.isoformat()

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

    env = Environment(loader=FileSystemLoader("."))
    for filter_name in jinja_filters.ALL_FILTERS:
        env.filters[filter_name] = getattr(jinja_filters, filter_name)

    template = env.get_template("templates/menu_template.j2")
    rendered_html = template.render(data=yaml_dict)

    with open(output_html_path, "w", encoding="utf-8") as html_path:
        html_path.write(rendered_html)

    return yaml_dict


def generate_index_html(yaml_dicts: list[str], output_html_path: str) -> None:
    env = Environment(loader=FileSystemLoader("."))
    for filter_name in jinja_filters.ALL_FILTERS:
        env.filters[filter_name] = getattr(jinja_filters, filter_name)

    template = env.get_template("templates/index_template.j2")
    rendered_html = template.render(data=yaml_dicts)

    with open(output_html_path, "w", encoding="utf-8") as html_path:
        html_path.write(rendered_html)


def process_yaml_paths(input_dir: str, output_dir: str) -> None:
    yaml_dicts = []
    for root, _, files in os.walk(input_dir):
        for filename in files:
            if filename.endswith(".yaml"):
                input_path = os.path.join(root, filename)
                relative_path = os.path.relpath(input_path, input_dir)
                output_filename = os.path.splitext(relative_path)[0] + ".html"
                output_path = os.path.join(output_dir, output_filename)

                yaml_dict = generate_menu_html(input_path, output_path)
                yaml_dict["_output_filename"] = output_filename
                yaml_dicts.append(yaml_dict)

                print(f"Processed: {input_path} -> {output_path}")

    output_path = os.path.join(output_dir, "index.html")
    generate_index_html(yaml_dicts, output_path)
    print(f"Processed: {output_path}")


def prepare_output_dir(output_dir: str) -> None:
    os.makedirs(output_dir, exist_ok=True)

    # cp -r ./static/ -> ./output/static/
    output_static_dir = os.path.join(output_dir, STATIC_DIR)
    if os.path.exists(output_static_dir):
        shutil.rmtree(output_static_dir)

    shutil.copytree(STATIC_DIR, output_static_dir)


if __name__ == "__main__":
    if len(sys.argv) > 4:
        print("Usage: python main.py [input_dir] [output_dir]")
        sys.exit(1)

    input_dir = sys.argv[1] if len(sys.argv) >= 2 else INPUT_DIR
    output_dir = sys.argv[2] if len(sys.argv) >= 3 else OUTPUT_DIR

    prepare_output_dir(output_dir)
    process_yaml_paths(input_dir, output_dir)
