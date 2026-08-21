import re

def find_deadline(text):
    patterns=[
        r'deadline.{0,100}',
        r'apply by.{0,100}',
        r'closing date.{0,100}'
    ]

    for p in patterns:
        result=re.search(p,text.lower())
        if result:
            return result.group()

    return "Not detected"


def funding_level(text):

    text=text.lower()

    if "fully funded" in text:
        return "Confirmed"

    if any(x in text for x in [
        "stipend",
        "salary",
        "studentship"
    ]):
        return "High"

    if "scholarship" in text:
        return "Medium"

    return "Unknown"
