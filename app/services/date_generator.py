from datetime import date, timedelta


def generate_date_combinations(
    earliest_departure: date, latest_departure: date, min_trip_days: int, max_trip_days: int, latest_return: date
):
    departure = earliest_departure
    while departure <= latest_departure:
        for days in range(min_trip_days, max_trip_days + 1):
            returning = departure + timedelta(days=days)
            if returning <= latest_return:
                yield departure, returning
        departure += timedelta(days=1)


class DateGenerator:
    generate = staticmethod(generate_date_combinations)
