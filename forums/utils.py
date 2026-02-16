def calculate_ring(activity_score):
    if activity_score >= 100:
        return "PLATINUM"
    elif activity_score >= 60:
        return "GOLD"
    elif activity_score >= 30:
        return "SILVER"
    elif activity_score >= 10:
        return "BRONZE"
    return "GRAY"
