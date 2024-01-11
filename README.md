# menudb

## Set Up Development Environment

    python3 -m venv env
    source env/bin/activate
    pip install -r requirements.txt

## Generate Static HTML Pages

Run:

    python main.py

The program reads YAML files from the `content/` subdirectory. Each YAML contains the contents of a transcribed restaurant menu in "raw" form. The program generates HTML pages and writes them to the `output/` subdirectory.

During processing, each menu item name is matched with dishes defined in `data/known_dishes.tsv`, which is a snapshot copy of https://docs.google.com/spreadsheets/d/1p_pUiqP6fgpCcKsQ4Ok7WpijfDf6fmVvRuJAwMi1B1E/edit#gid=2051976005. (NOTE: As it's easier to edit in Google Sheets, treat Google Sheets as the canonical version and use that to overwrite `data/known_dishes.tsv`, rather than the other way around.)

Upon `git push`, all of `output/` is published (via GitHub Actions defined in `.github/`) to https://foodtbd.github.io/menudb/.


## Menu YAML

Each YAML file contains **restaurant** metadata coupled with a **menu** definition.  A menu contains **pages**. A page contains **sections**. A section contains **menu items**, a.k.a. dishes.

### Example

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
        doordash_url: https://www.doordash.com/xxx
    menu:
        # See Style Guide below
        language_codes:
            - zh-Hans
            - en-US
        pages:
            # Alternatively use `page_url` to show a page within an IFRAME
            - page_image_url: https://www.example.com/menu.jpg
              sections:
                # All fields are optional
                - item_number: D101

                  # The following fields will take precedence over matching data from `known_dishes.tsv`.
                  # The key suffix must match one of the above `language_codes`.
                  # The name and description values may contain Markdown-style bold, italic, code, and links
                  "name_zh-Hans": 酸菜鱼
                  "name_en": Boiled fish with [pickled cabbage](https://en.wikipedia.org/wiki/Suan_cai) and chili
                  "description_en": Lorem ipsum dolor sit amet, consectetur adipiscing elit.
                  wikipedia_url_en: https://en.wikipedia.org/wiki/Dumpling

                  # The following fields are non-localizable
                  image_url: https://www.example.com/dish.jpg
                  note: Excepteur sint occaecat
                  price: (SP)
                  price_note: "(Lorem ipsum)"
                  spice_heat_level: 1

        # The following fields are optional
        page_footer: Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore.

The YAML is actually [StrictYAML](https://hitchdev.com/strictyaml/). Each input YAML gets validated against the schema definition in `schema.py`.

### Style Guide

**Languages**: Language codes are [BCP 47 language tags](https://en.wikipedia.org/wiki/IETF_language_tag), specifying the language of the native dish name.

Language Code | Meaning
----- | -----
`en-US` | English (United States)
`zh-Hans` | Simplified Chinese [written form]
`zh-Hant` | Traditional Chinese [written form]

**Menu images**: See repository https://github.com/FoodTBD/menudb_images.

**Dish names**:
* Any spelling mistakes in the original menu should be transcribed verbatim and annotated with `[sic]`.
* Any notes like "half portion" written in the dish name should be moved to `description_xxx` or `note_xxx` fields.

**Dish images**: Either link directly to the restaurant's own website, or otherwise use free licensed content, ideally from Wikipedia Commons of the form https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/filename.jpg/600px-filename.jpg.

### Transcription Workflow

John's workflow:

1. Upload menu photos to Google Drive.
2. On phone: using the Google Drive app, choose "Open with", then "Google Lens". (Alternatively open the image file within the Google Translate app.) Tap "Select text".
3. Send the copied text to Mac.
4. On Mac: use the text from Google Lens/Translate to fill out the YAML.
5. Open the menu photo in the macOS Preview app. Select dish names and copy to clipboard. Double-check the OCR text from Google Lens/Translate against the OCR text from Preview. If they disagree, use Google Translate and Google Search to figure out the correct transcription.
