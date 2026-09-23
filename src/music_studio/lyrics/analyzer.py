from collections import Counter
import re
import statistics
import unicodedata

def analyze_section(section):
    lines = section['lyrics']
    syllables = []
    for line in lines:
        normalized = unicodedata.normalize('NFC', line)
        count = sum('\uac00' <= c <= '\ud7a3' for c in normalized)
        syllables.append(count if count else None)
    counts = [x for x in syllables if x is not None]
    lengths = [len(line) for line in lines if line.strip()]
    words = Counter(re.findall(r'[^\W_]+', unicodedata.normalize('NFC', '\n'.join(lines)).casefold()))
    return dict(section_id=section['id'], lines_count=len(lengths), empty_lines=sum(not x.strip() for x in lines),
                characters_count=sum(map(len, lines)), approximate_syllables_per_line=syllables,
                average_syllables=round(statistics.mean(counts), 2) if counts else None,
                line_length_variation=dict(min=min(lengths, default=0), max=max(lengths, default=0),
                                           stddev=round(statistics.pstdev(lengths), 2) if lengths else 0),
                repeated_words=[dict(word=w, count=n) for w, n in words.most_common(20) if n > 1])
