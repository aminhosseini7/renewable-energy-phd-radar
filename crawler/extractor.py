import re

def funding_score(text):
    words=[
        "funded",
        "stipend",
        "salary",
        "scholarship",
        "studentship",
        "phd position"
    ]

    found=[w for w in words if w in text.lower()]
    return min(len(found)*20,100), found


def deadline(text):
    patterns=[
        r'deadline.{0,80}',
        r'apply by.{0,80}',
        r'closing date.{0,80}'
    ]

    for p in patterns:
        m=re.search(p,text.lower())
        if m:
            return m.group()

    return "Unknown"
