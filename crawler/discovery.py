def find_vacancy_links(text):
    keys=[
        "phd",
        "doctoral",
        "research scholarship",
        "vacancy",
        "position"
    ]

    return [
        line.strip()
        for line in text.split("\n")
        if any(k in line.lower() for k in keys)
    ]
