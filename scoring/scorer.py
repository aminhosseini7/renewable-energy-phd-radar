import yaml

def score(text):

    text=text.lower()
    total=0
    matched=[]

    with open("config/keywords.yaml",encoding="utf8") as f:
        keys=yaml.safe_load(f)

    for k,v in keys["keywords"].items():
        if k.lower() in text:
            total += v
            matched.append(k)

    return min(total,100), matched
