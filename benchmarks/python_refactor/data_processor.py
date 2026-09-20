def process_data(items):
    result = []
    for item in items:
        if item % 2 == 0:
            val = item * 2
            result.append(val)
        else:
            val = item * 3
            result.append(val)
    return result


def calculate_total(data):
    total = 0
    for d in data:
        total = total + d
    return total


def get_stats(data):
    s = 0
    for x in data:
        s = s + x
    avg = s / len(data) if data else 0
    mx = data[0] if data else 0
    for x in data:
        if x > mx:
            mx = x
    return {"sum": s, "average": avg, "max": mx}