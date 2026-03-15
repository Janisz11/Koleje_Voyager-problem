#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import math


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    
    R = 6_371_000

    φ1 = math.radians(lat1)
    φ2 = math.radians(lat2)
    dφ = math.radians(lat2 - lat1)
    dλ = math.radians(lon2 - lon1)

    a = math.sin(dφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(dλ / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))

    return R * c


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
  
    return haversine(lat1, lon1, lat2, lon2) / 1000
