#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from datetime import date


def is_service_active(service_id: str, travel_date: date,
                      calendar: dict, cal_dates: dict) -> bool:
    ymd = travel_date.strftime("%Y%m%d")

    for exc in cal_dates.get(service_id, []):
        if exc["date"] == ymd:
            return exc["type"] == 1

    cal = calendar.get(service_id)
    if not cal:
        return False

    if ymd < cal["start"] or ymd > cal["end"]:
        return False

    return cal["days"][travel_date.weekday()] == 1
