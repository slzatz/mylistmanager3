def age(int z):

    if z > 700:
        return "2 years..."
    elif z > 365:
        return "A year +"
    elif z > 60:
        return "{} months".format(z/30)
    elif z > 40:
        return "{} weeks".format(z/7)
    elif z > 27:
        return "1 month"
    elif z >13:
        return "{} weeks".format(z/7)
    if z > 6:
        return "1 week"
    elif z > 1:
        return "{} days".format(z)
    elif z == 1:
        return "yesterday"
    else:
        return "today"