import datetime
import re
from markupsafe import Markup


def styled_text_format(text: str) -> str:
    # Replace Markdown-style **bold**, *italic*, `code`, and links with HTML tags

    def replace_markup(match: re.Match[str]) -> str:
        if match.group(1):
            return "<strong>" + match.group(1) + "</strong>"
        elif match.group(2):
            return "<em>" + match.group(2) + "</em>"
        elif match.group(3):
            return "<code>" + match.group(3) + "</code>"
        else:
            raise NotImplementedError

    # Match Markdown styling
    pattern = r"\*\*(.*?)\*\*|\*(.*?)\*|`(.*?)`"
    html_text = re.sub(pattern, replace_markup, text)

    def replace_link(match):
        link_text, link_url = match.groups()
        return f'<a href="{link_url}" target="_blank" rel="noopener">{link_text}</a>'

    # Match Markdown links
    markdown_link_pattern = r"\[([^\]]+)\]\(([^)]+)\)"
    html_text = re.sub(markdown_link_pattern, replace_link, html_text)

    return Markup(html_text)


def iso8601_to_datetime(iso8601_str: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(iso8601_str)


def datetime_format(dt: datetime.datetime, format="%Y-%m-%d %H:%M") -> str:
    return dt.strftime(format)


def pretty_url(url: str) -> str:
    # Remove 'https://www.' part of URL as well as trailing '/'
    return url.replace("//www.", "//").replace("https://", "").rstrip("/")


ALL_FILTERS = [
    "styled_text_format",
    "iso8601_to_datetime",
    "datetime_format",
    "pretty_url",
]
