import re

def funding(text):
    t=text.lower()
    if "fully funded" in t:
        return "Fully funded"
    if "stipend" in t or "salary" in t:
        return "Funded"
    if "scholarship" in t:
        return "Scholarship"
    return "Unknown"

def deadline(text):
    for p in [r"deadline.{0,100}", r"apply by.{0,100}"]:
        m=re.search(p,text.lower())
        if m:
            return m.group()
    return "Unknown"

def title(text):
    for line in text.split("\n"):
        if "phd" in line.lower():
            return line[:200]
    return "PhD opportunity"
