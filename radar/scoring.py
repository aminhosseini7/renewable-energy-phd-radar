def score(text):
    text=text.lower()
    points=0
    rules={
    'saf':30,
    'hefa':25,
    'milp':20,
    'stochastic':20,
    'supply chain':20,
    'biomass':15,
    'bioenergy':15
    }
    for k,v in rules.items():
        if k in text:
            points+=v
    return min(points,100)