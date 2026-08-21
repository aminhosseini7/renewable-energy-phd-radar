def extract_title(text):

    lines=[x.strip() for x in text.split("\n") if x.strip()]

    for line in lines[:30]:
        if "phd" in line.lower():
            return line

    return "PhD opportunity"


def extract_supervisor(text):

    keywords=[
        "supervisor",
        "principal investigator",
        "contact"
    ]

    for line in text.split("\n"):
        if any(k in line.lower() for k in keywords):
            return line.strip()

    return "Unknown"
