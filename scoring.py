import yaml

def score(text):

    with open("config/keywords.yaml",encoding="utf8") as f:
        cfg=yaml.safe_load(f)

    text=text.lower()
    total=0
    matches=[]

    for k,v in cfg["research"].items():
        if k in text:
            total+=v
            matches.append(k)

    return min(total,100), matches
