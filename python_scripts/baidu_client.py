#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
百度地图 Web API 客户端。
"""

import time

import requests


class BaiduClient:
    def __init__(self, ak: str, timeout: int = 15, min_interval_seconds: float = 1.0):
        if not ak:
            raise ValueError('缺少百度地图 AK')
        self.ak = ak
        self.timeout = timeout
        self.min_interval_seconds = max(float(min_interval_seconds), 0.0)
        self._last_request_monotonic = None

    def _request(self, url: str, params: dict):
        self._throttle()
        final_params = {'ak': self.ak, 'output': 'json'}
        final_params.update(params)

        response = requests.get(url, params=final_params, timeout=self.timeout)
        self._last_request_monotonic = time.monotonic()
        response.raise_for_status()
        data = response.json()

        if data.get('status') != 0:
            raise RuntimeError(
                f"百度接口调用失败: url={url}, status={data.get('status')}, message={data.get('message')}"
            )

        return data

    def _throttle(self):
        if self._last_request_monotonic is None or self.min_interval_seconds <= 0:
            return

        elapsed = time.monotonic() - self._last_request_monotonic
        remaining = self.min_interval_seconds - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def geocode(self, address: str, city: str = '上海'):
        data = self._request(
            'https://api.map.baidu.com/geocoding/v3/',
            {
                'address': address,
                'city': city,
            }
        )
        result = data.get('result') or {}
        location = result.get('location')
        if not location:
            raise RuntimeError(f'地理编码失败: {address}')
        return result

    def driving(self, origin: str, destination: str, departure_timestamp: int):
        data = self._request(
            'https://api.map.baidu.com/direction/v2/driving',
            {
                'origin': origin,
                'destination': destination,
                'coord_type': 'bd09ll',
                'ret_coordtype': 'bd09ll',
                'tactics': 13,
                'alternatives': 0,
                'steps_info': 0,
                'departure_time': str(departure_timestamp),
            }
        )
        routes = (data.get('result') or {}).get('routes') or []
        if not routes:
            raise RuntimeError(f'驾车路径规划失败: {origin} -> {destination}')
        return routes[0]

    def transit(self, origin: str, destination: str, departure_date: str, departure_time: str):
        data = self._request(
            'https://api.map.baidu.com/direction/v2/transit',
            {
                'origin': origin,
                'destination': destination,
                'coord_type': 'bd09ll',
                'ret_coordtype': 'bd09ll',
                'departure_date': departure_date,
                'departure_time': departure_time,
                'tactics_incity': 4,
                'page_size': 10,
                'page_index': 1,
            }
        )
        routes = (data.get('result') or {}).get('routes') or []
        if not routes:
            raise RuntimeError(f'公交路径规划失败: {origin} -> {destination}')
        return routes
