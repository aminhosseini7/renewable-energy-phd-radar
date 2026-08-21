import yaml

def score(text):

    with open(
        'config/profile.yaml',
        encoding='utf8'
    ) as f:
        profile=yaml.safe_load(f)

    words=[]

    for group in profile['profile'].values():
        words.extend(group)

    hits=[
        x for x in words
        if x.lower() in text.lower()
    ]

    return min(len(hits)*8,100), hits
