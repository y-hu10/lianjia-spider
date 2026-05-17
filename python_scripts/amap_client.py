#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
高德 Web Service API 客户端。
"""

import requests


class AmapClient:
    BASE_URL = 'https://restapi.amap.com'

    def __init__(self, api_key: str, timeout: int = 15):
        if not api_key:
            raise ValueError('缺少高德 API key')
        self.api_key = api_key
        self.timeout = timeout

    def _request(self, path: str, params: dict):
        final_params = {'key': self.api_key, 'output': 'JSON'}
        final_params.update(params)

        response = requests.get(
            f'{self.BASE_URL}{path}',
            params=final_params,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()

        if data.get('status') != '1':
            raise RuntimeError(
                f"高德接口调用失败: path={path}, info={data.get('info')}, infocode={data.get('infocode')}"
            )

        return data

    def geocode(self, address: str):
        data = self._request('/v3/geocode/geo', {'address': address})
        geocodes = data.get('geocodes') or []
        if not geocodes:
            raise RuntimeError(f'地理编码失败: {address}')
        return geocodes[0]

    def driving(self, origin: str, destination: str):
        data = self._request(
            '/v3/direction/driving',
            {
                'origin': origin,
                'destination': destination,
                'extensions': 'base',
            }
        )
        paths = (data.get('route') or {}).get('paths') or []
        if not paths:
            raise RuntimeError(f'驾车路径规划失败: {origin} -> {destination}')
        return paths[0]

    def transit(self, origin: str, destination: str):
        data = self._request(
            '/v3/direction/transit/integrated',
            {
                'origin': origin,
                'destination': destination,
                'city': '上海',
                'cityd': '上海',
                'extensions': 'all',
            }
        )
        transits = (data.get('route') or {}).get('transits') or []
        if not transits:
            raise RuntimeError(f'公交路径规划失败: {origin} -> {destination}')
        return transits
