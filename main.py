import datetime
import os
import sys
import typing
import urllib.parse
from typing import Any, OrderedDict

import strictyaml
from jinja2 import Environment, FileSystemLoader

from jinja_filters import format_styled_text, prettify_url


def generate_html(
    input_yaml_path: str, output_html_path: str, template_path: str
) -> None:
    with open(input_yaml_path, "r", encoding="utf-8") as yaml_path:
        yaml_data = strictyaml.load(yaml_path.read(), label="!yaml")

    mod_date = datetime.datetime.fromtimestamp(os.path.getmtime(input_yaml_path))
    # The type checker thinks yaml_data.data is a str, not a dict
    yaml_dict = typing.cast(OrderedDict[str, Any], yaml_data.data)

    # Inject the modification date into the YAML data
    yaml_dict["date_modified"] = mod_date.isoformat()

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
    env.filters["format_styled_text"] = format_styled_text
    env.filters["prettify_url"] = prettify_url

    template = env.get_template(template_path)
    rendered_html = template.render(data=yaml_dict)

    with open(output_html_path, "w", encoding="utf-8") as html_path:
        html_path.write(rendered_html)


def process_yaml_paths(input_dir: str, output_dir: str, template: str) -> None:
    os.makedirs(output_dir, exist_ok=True)

    for root, _, files in os.walk(input_dir):
        for filename in files:
            if filename.endswith(".yaml"):
                input_path = os.path.join(root, filename)
                relative_path = os.path.relpath(input_path, input_dir)
                output_path = os.path.join(
                    output_dir, os.path.splitext(relative_path)[0] + ".html"
                )

                generate_html(input_path, output_path, template)
                print(f"Processed: {input_path} -> {output_path}")


if __name__ == "__main__":
    if len(sys.argv) > 4:
        print("Usage: python main.py [input_dir] [output_dir] [menu_template.j2]")
        sys.exit(1)

    input_dir = sys.argv[1] if len(sys.argv) >= 2 else "content"
    output_dir = sys.argv[2] if len(sys.argv) >= 3 else "output"
    template = sys.argv[3] if len(sys.argv) == 4 else "templates/menu_template.j2"

    process_yaml_paths(input_dir, output_dir, template)
