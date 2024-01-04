import re
from markupsafe import Markup


def format_styled_text(text: str):
    # Replace **bold**, *italic*, and `code` with HTML tags

    def replace_markup(match: re.Match[str]) -> str:
        if match.group(1):
            return "<strong>" + match.group(1) + "</strong>"
        elif match.group(2):
            return "<em>" + match.group(2) + "</em>"
        elif match.group(3):
            return "<code>" + match.group(3) + "</code>"
        else:
            raise NotImplementedError

    pattern = r"\*\*(.*?)\*\*|\*(.*?)\*|`(.*?)`"
    formatted_text = re.sub(pattern, replace_markup, text)

    return Markup(formatted_text)


def prettify_url(url: str):
    # Remove 'https://www.' part of URL as well as trailing '/'
    return url.replace("//www.", "//").replace("https://", "").rstrip("/")
