# menudb

## Set Up Development Environment

    python3 -m venv env
    source env/bin/activate
    pip install -r requirements.txt

## Generate HTML

Run:

    python main.py

The program reads from the `content/` subdirectory, which contains YAML representing each restaurant menu in "raw" form. The program generates HTML and writes it to the `output/` subdirectory.

During processing, each menu item name is matched with dishes defined in `data/known_dishes.tsv`, which is a snapshot copy of https://docs.google.com/spreadsheets/d/1p_pUiqP6fgpCcKsQ4Ok7WpijfDf6fmVvRuJAwMi1B1E/edit#gid=2051976005. NOTE: As it's easier to edit in Google Sheets, treat Google Sheets as the canonical version and use that to overwrite `data/known_dishes.tsv`, rather than the other way around.

Upon `git push` (via GitHub Actions), all of `output/` is published to https://foodtbd.github.io/menudb/index.html.


## Menu Definition

Information hierarchy: Each YAML file contains **restaurant** metadata coupled with a **menu** definition.  Each menu contains **pages**. Each page contains **sections**. Each section contains **menu items** a.k.a. dishes.

The YAML is [StrictYAML](https://hitchdev.com/strictyaml/).  

Here's an example with all the defined fields:

    author: Harry Q. Bovik
    restaurant:
        name: Jade Garden Restaurant
        street_address: 123 Main St.
        city: San Jose, CA
        country_code: US

        # The following fields are optional
        tags: chinese, cantonese
        homepage_url: https://www.example.com/
        facebook_url: https://www.facebook.com/xxx
        instagram_url: https://www.instagram.com/xxx
    menu:
        language_codes:
            # Simplified Chinese [written form]
            - zh-Hans
            - en-US
        pages:
            # Alternatively use page_url to show a page within an IFRAME
            - page_image_url: https://www.example.com/menu.jpg
              sections:
                - item_number: D101
                  # The following fields will take precedence over matching data from `known_dishes.tsv`.
                  # The key suffix must match one of the above `language_codes`.
                  # The name and description values may contain Markdown-style bold, italic, code, and links
                  "name_zh-Hans": 酸菜鱼
                  "name_en": Boiled fish with [pickled cabbage](https://en.wikipedia.org/wiki/Suan_cai) and chili
                  "description_en": Lorem ipsum dolor sit amet, consectetur adipiscing elit.
                  wikipedia_url_en: https://en.wikipedia.org/wiki/Dumpling

                  # The following fields are non-localized
                  image_url: https://www.example.com/dish.jpg
                  note: Excepteur sint occaecat
                  price: (SP)
                  price_note: "(Lorem ipsum)"
                  spice_heat_level: 1
        page_footer: Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore.

Dish names: Any spelling or grammar mistakes in the original menu should be transcribed verbatim and annotated with `[sic]`. Any notes like "half portion" in the dish name should be moved to `description_xxx` or `note_xxx` fields.

Languages: Language codes are [BCP 47 language tags](https://en.wikipedia.org/wiki/IETF_language_tag), specifying the native origin of the dish name. Examples:
* `en-US` means English (United States)
* `zh-Hans` means Simplified Chinese [written form]
* `zh-Hant` means Traditional Chinese [written form]

Images: To provide images, either link directly to the restaurant's own website, or otherwise they should be freely licensed content, ideally from Wikipedia Commons of the form https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/filename.jpg/128px-filename.jpg. Specify `128px-` for thumbnails.


## To Do

* Fix broken responsiveness on mobile
* Add data and test
    * add more menus (add YAML)
    * fill-out/improve the known_dishes
    * dogfood the generated pages, think of more improvements, repeat
* Add index nav link
* Add known dishes / "EatsDB" page
* Google Analytics
* Cantonese TTS?
* Add feedback link