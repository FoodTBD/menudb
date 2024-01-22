# MenuDB

## Setting Up Development Environment

    python3 -m venv env
    source env/bin/activate
    pip install -r requirements.txt


## Generating HTML Pages

Run:

    python main.py

The program reads YAML files from the `content/` subdirectory. Each YAML contains transcribed restaurant menu data in raw form. From this data, the program generates static HTML pages and writes them to the `output/` subdirectory.

(The YAML is actually [StrictYAML](https://hitchdev.com/strictyaml/). Each input YAML gets validated against the schema definition in `schema.py`.)

During processing, each menu item name is matched against data (both single word terms as well as full dish names) defined in `data/known_terms.tsv`.

At this point, you should be able to open `output/index.html` in your web browser:

    open output/index.html


## Publishing (via GitHub Pages)

Upon `git push`, all of `output/` is published to https://foodtbd.github.io/menudb/. This process is implemented via GitHub Actions (defined in `.github/`).


## Menu YAML

Each YAML file contains **restaurant** metadata coupled with a **menu** definition.  A **menu** contains **pages**. A page contains **sections**. A section contains **menu items**, a.k.a. dishes.


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
        online_menu_url: https://www.example.com/xxx
        yelp_url: https://www.yelp.com/xxx
        tripadvisor_url: https://www.tripadvisor.com/xxx
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

                  # The following fields will take precedence over matching data from `known_terms.tsv`.
                  # The key suffix must match one of the above `language_codes`.
                  # The name and description values may contain Markdown-style bold, italic, code
                  "name_zh-Hans": 酸菜鱼
                  "name_en": Boiled fish with pickled cabbage and chili
                  "description_en": Lorem ipsum dolor sit amet, consectetur adipiscing elit.
                  wikipedia_url: https://en.wikipedia.org/wiki/Dumpling

                  # The following fields are non-localizable
                  image_url: https://www.example.com/dish.jpg
                  note: Excepteur sint occaecat
                  price: $8.88
                  price_note: "(Lorem ipsum)"
                  spice_heat_level: 1

        # The following fields are optional
        page_footer: Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore.

### Menu YAML Style Guide

#### Language Codes (`language_codes` Field)

Language codes are [BCP 47 language tags](https://en.wikipedia.org/wiki/IETF_language_tag), specifying the language of the native dish name.

Language Code | Meaning
----- | -----
`en-US` | English (United States)
`zh-Hans` | Simplified Chinese [written form][*](https://www.loc.gov/standards/iso639-2/faq.html#23)
`zh-Hant` | Traditional Chinese [written form][*](https://www.loc.gov/standards/iso639-2/faq.html#23)

#### Menu Images (`page_image_url` Field)

See repository https://github.com/FoodTBD/menudb_images.

#### Dish Names (`name_{$LANG}` Fields)

* Anything like quantities or "half portion" written in a dish name should be moved to `description_xxx` or `note_xxx` fields, to facilitate dictionary-based matching.
* Any spelling mistakes in the original menu should be transcribed verbatim and annotated with `[sic]`.


## Language Data

`known_terms.tsv` contains all linguistic definitions, including for dishes. It supercedes `known_dishes.tsv`.

`known_terms.tsv` is a snapshot copy of https://docs.google.com/spreadsheets/d/1p_pUiqP6fgpCcKsQ4Ok7WpijfDf6fmVvRuJAwMi1B1E/edit#gid=2051976005. As it's easier to edit in Google Sheets, treat Google Sheets as the canonical version and use that to overwrite `data/known_terms.tsv`, rather than the other way around.

There's a grey zone between what is a "term" and what is a "dish". For example, "braised" is obviously a term, and "Kung Pao Chicken" is obviously a dish. Some things like "fried rice" and "wonton" and "bok choy" SHOULD be left as terms, rather than dishes, because they are usually only part of a dish name.

To define a **term**:
1. Write the `en` name in lowercase.
1. Leave the `dish_cuisine` and `dish_description_en` fields unset.

To promote a term to a **dish**:
1. Write the `en` name in title-case.
1. Fill out the `dish_cuisine` and `dish_description_en` fields.


### Language Data Style Guide

#### `zh-Hans` and `zh-Hant` Columns

* Use Google Translate to translate between simplified and traditional Chinese.
* Minor variations in written form MAY be added using in comma separated format, e.g. (`煎䭔,煎堆` for jiān duī). Use separate line items for synonyms, especially if they correspond to separate entries in Wiktionary, e.g. (`煎䭔` jiān duī vs `芝麻球` for zhīma qiú).

#### `en` Column

* Use Google Search and ChatGPT to come up with the best translation for food contexts.
* Write nouns in singular form ("noodle", not "noodles"), and verbs in past tense form ("roasted" not "roast").
* Write dish names in title-case ("Hot and Sour Soup"). (Articles e.g. "a", "an", "the", and conjunctions e.g. "and", "with", etc. are excluded.) Write all other terms in lowercase ("braised"). 

#### `wikipedia_url` Column

* Prefer English Wikipedia. However, if there's a relevant article in another language Wikipedia, use it and it will be presented to the user via Google Translate.
* Use the most specific Wikipedia link e.g. https://en.wikipedia.org/wiki/Nian_gao#Jiangnan_and_Shanghainese_cuisine.

#### `image_url` Column

Either link directly to the restaurant's own website, or otherwise use free licensed content, ideally from Wikipedia Commons of the form `https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/filename.jpg/600px-filename.jpg`.

* Use Google Image Search for "`site:wikipedia.org OR site:wikimedia.org XXX`" to find images.

#### `dish_cuisine` Column

Use [BCP 47 language tags](https://en.wikipedia.org/wiki/IETF_language_tag), specifying the geographic region of the cuisine.

Language Code | Meaning
----- | -----
`zh` | Chinese (cuisine of the Chinese diaspora, including outside of People's Republic of China)
`zh-u-sd-cngd` | Chinese ([Guangdong province](https://en.wikipedia.org/wiki/Guangdong)), i.e. Cantonese cuisine
`zh-u-sd-cnjs` | Chinese ([Jiangsu province](https://en.wikipedia.org/wiki/Jiangsu)), i.e. Jiangsu cuisine
`zh-u-sd-cnsc` | Chinese ([Sichuan province](https://en.wikipedia.org/wiki/Sichuan)), i.e. Szechuan cuisine

See https://www.unicode.org/cldr/charts/43/supplemental/territory_subdivisions.html#CN for additional country subdivision codes.

Locales are defined in the `known_locales.tsv`, which comes from the same Google Sheet as `known_terms.tsv`.

#### `dish_description_en` Column

Use ChatGPT to generate concise descriptions with an encyclopedic voice. Keep the description to around 50-75 characters. Omit filler words like "delicious", "Chinese".


## Transcription Workflow

John's workflow:

1. Use OCR to do the transcription. Google Lens/Translate seems to work best, but you might want to double-check against macOS Preview and/or [EasyOCR](https://www.jaided.ai/easyocr/).
    * To use Google Lens/Translate: Upload menu photos to Google Drive. On phone: using the Google Drive app, choose "Open with", then "Google Lens". (Alternatively open the image file within the Google Translate app.) Tap "Select text". Send the copied text to Mac.
    * To use macOS Preview: Open the menu photo in Preview. Select dish names and copy to clipboard.
2. Ask ChatGPT to "`Translate literally: xxx`".
    * Read the answer and do a sanity check. Look up terms in [Wiktionary](https://en.wiktionary.org/), Wikipedia, Google Search, and/or Google Image Search, even [MDBG Chinese Dictionary](https://www.mdbg.net/chinese/dictionary?page=radicals). If something doesn't make sense, go back and look for OCR errors.
3. Add any useful terms to the `known_terms` table, especially if it exists in Wiktionary. See style guide above.
4. Proofread (and dogfood) the generated results to look for errors ("char siu with vegetarian goose"?!) and think of usability improvements.
