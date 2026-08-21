import yaml

def research_score(text):

    with open("config/keywords.yaml",encoding="utf8") as f:
        cfg=yaml.safe_load(f)

    score=0
    matches=[]

    text=text.lower()

    for k,v in cfg["research"].items():
        if k in text:
            score+=v
            matches.append(k)

    return min(score,100),matches
