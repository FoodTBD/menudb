from collections import defaultdict


def _generate_ngrams(text: str, n: int) -> list[str]:
    ngrams = []
    for i in range(len(text) - n + 1):
        ngram = text[i : i + n]
        ngrams.append(ngram)
    return ngrams


def find_top_ngrams(
    strings: list[str], n: int, top_n: int = 10
) -> list[tuple[str, int]]:
    ngram_counts = defaultdict(int)
    for string in strings:
        ngrams = _generate_ngrams(string, n)
        for ngram in ngrams:
            ngram_counts[ngram] += 1

    # Get the top n-grams
    sorted_ngrams = sorted(ngram_counts.items(), key=lambda x: x[1], reverse=True)
    top_ngrams = sorted_ngrams[:top_n]

    return top_ngrams
