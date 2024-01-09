# menudb

## Set Up Development Environment

    python3 -m venv env
    source env/bin/activate
    pip install -r requirements.txt

## Generate HTML

Run:

    python main.py

The program reads from the `content/` subdirectory, which contains YAML representing each restaurant menu in "raw" form. The program generates HTML and writes it to the `output/` subdirectory.

During processing, each menu item name is matched with dishes defined in `data/known_dishes.tsv`, which is a snapshot copy of https://docs.google.com/spreadsheets/d/1p_pUiqP6fgpCcKsQ4Ok7WpijfDf6fmVvRuJAwMi1B1E/edit#gid=2051976005.


Upon `git push` (via GitHub Actions), all of `output/` is published to https://foodtbd.github.io/menudb/index.html.


## Menu Definition

The YAML is [StrictYAML](https://hitchdev.com/strictyaml/).  

Information hierarchy: Each YAML file contains **restaurant** metadata coupled with a **menu** definition.  Each menu contains **pages**. Each page contains **sections**. Each section contains **menu items** a.k.a. dishes.

Languages: Language codes are [BCP 47 language tags](https://en.wikipedia.org/wiki/IETF_language_tag), specifying the native origin of the dish name. Examples:
* `en-US` means English (United States)
* `zh-Hans` means Simplified Chinese [written form]
* `zh-Hant` means Traditional Chinese [written form]

Images: To provide images, either link directly to the restaurant's own website, or otherwise they should be freely licensed content, ideally from Wikipedia Commons of the form https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/filename.jpg/128px-filename.jpg. Specify `128px-` for thumbnails.


## To Do

* Add index nav link
* Add known dishes / "EatsDB" page
* Google Analytics
* Cantonese TTS?
