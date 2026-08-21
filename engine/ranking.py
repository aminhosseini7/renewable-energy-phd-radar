import yaml

def rank(text):

    with open("config/profile.yaml",encoding="utf8") as f:
        cfg=yaml.safe_load(f)

    score=0
    matches=[]

    for k in cfg["profile"]["keywords"]:
        if k.lower() in text.lower():
            score += 8
            matches.append(k)

    return min(score,100), matches
