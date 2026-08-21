import yaml

def score(text):
    with open("config/profile.yaml",encoding="utf8") as f:
        keys=yaml.safe_load(f)["candidate"]["keywords"]

    hits=[k for k in keys if k.lower() in text.lower()]
    return min(len(hits)*8,100), hits
