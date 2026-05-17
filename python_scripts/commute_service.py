#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
小区通勤信息服务。
"""

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from baidu_client import BaiduClient


ROUTE_PROVIDER = 'baidu'
REFERENCE_RULE = 'MONDAY_09:00'
SHANGHAI_TZ = ZoneInfo('Asia/Shanghai')


def _normalize_shanghai_address(address: str) -> str:
    cleaned = str(address or '').strip()
    if not cleaned:
        return cleaned
    if '上海' in cleaned:
        return cleaned
    return f'上海{cleaned}'


def _community_query(location: str) -> str:
    return _normalize_shanghai_address(location)


def _next_monday_nine():
    now = datetime.now(SHANGHAI_TZ)
    days_ahead = (7 - now.weekday()) % 7
    candidate = (now + timedelta(days=days_ahead)).replace(
        hour=9, minute=0, second=0, microsecond=0
    )

    if candidate <= now:
        candidate = candidate + timedelta(days=7)

    return candidate


def _format_baidu_coord(location: dict) -> str:
    return f"{location['lat']:.6f},{location['lng']:.6f}"


def build_house_commute_values(workplaces, commute_records):
    values = {}
    for workplace in workplaces:
        code = workplace['code']
        record = commute_records.get(code)
        values[f'commute_{code}_driving_duration'] = (
            None if not record else record['driving_duration_sec']
        )
        values[f'commute_{code}_transit_duration'] = (
            None if not record else record['transit_duration_sec']
        )
    return values


class CommuteService:
    def __init__(self, db, config, logger):
        self.db = db
        self.logger = logger
        self.workplaces = db.workplaces
        self.client = BaiduClient(config['baidu_ak'])
        self.cache = {}

    def apply_house_commute(self, house: dict):
        records = self.ensure_community_commutes(
            region=house['house_region'],
            location=house['house_location'],
        )
        house.update(build_house_commute_values(self.workplaces, records))
        return house

    def ensure_community_commutes(self, region: str, location: str, force_refresh: bool = False):
        records = {}
        for workplace in self.workplaces:
            cache_key = (region, location, workplace['code'], force_refresh)
            if cache_key not in self.cache:
                try:
                    self.cache[cache_key] = self._get_or_create_commute(
                        region=region,
                        location=location,
                        workplace=workplace,
                        force_refresh=force_refresh,
                    )
                except Exception as exc:
                    self.logger.error(
                        f"通勤信息生成失败: {region}/{location} -> {workplace['name']}: {exc}"
                    )
                    self.cache[cache_key] = None
            records[workplace['code']] = self.cache[cache_key]
        return records

    def sync_all_houses(self, force_refresh: bool = True):
        communities = self.db.fetchDistinctCommunities()
        total = len(communities)

        for idx, row in enumerate(communities, 1):
            region = row['REGION']
            location = row['LOCATION']
            self.logger.info(f'[{idx}/{total}] 同步通勤信息: {region}/{location}')

            try:
                records = self.ensure_community_commutes(
                    region=region,
                    location=location,
                    force_refresh=force_refresh,
                )
                values = build_house_commute_values(self.workplaces, records)
                self.db.updateHouseCommuteByCommunity(region, location, values)
            except Exception as exc:
                self.logger.error(f'同步失败: {region}/{location}: {exc}')

    def _needs_refresh(self, existing):
        if not existing:
            return True
        if existing['ROUTE_PROVIDER'] != ROUTE_PROVIDER:
            return True
        if existing['REFERENCE_RULE'] != REFERENCE_RULE:
            return True
        return False

    def _get_or_create_commute(self, region: str, location: str, workplace: dict, force_refresh: bool = False):
        existing = self.db.fetchCommunityCommute(region, location, workplace['code'])
        if existing and not force_refresh and not self._needs_refresh(existing):
            return self._row_to_commute_record(existing)

        self.logger.info(
            f"生成百度通勤缓存: {region}/{location} -> {workplace['name']}"
        )

        reference_dt = _next_monday_nine()
        community_query = _community_query(location)
        workplace_query = _normalize_shanghai_address(workplace['address'])

        community_geo = self.client.geocode(community_query)
        workplace_geo = self.client.geocode(workplace_query)

        community_coordinate = _format_baidu_coord(community_geo['location'])
        workplace_coordinate = _format_baidu_coord(workplace_geo['location'])

        driving = self.client.driving(
            community_coordinate,
            workplace_coordinate,
            departure_timestamp=int(reference_dt.timestamp()),
        )
        transit_routes = self.client.transit(
            community_coordinate,
            workplace_coordinate,
            departure_date=reference_dt.strftime('%Y-%m-%d'),
            departure_time='09:00',
        )
        best_transit = min(
            transit_routes,
            key=lambda item: int(item.get('duration') or 0)
        )

        now = datetime.now(SHANGHAI_TZ).strftime('%Y-%m-%d %H:%M:%S')
        record = {
            'region': region,
            'location': location,
            'workplace_code': workplace['code'],
            'workplace_name': workplace['name'],
            'route_provider': ROUTE_PROVIDER,
            'reference_rule': REFERENCE_RULE,
            'reference_departure_at': reference_dt.strftime('%Y-%m-%d %H:%M:%S'),
            'community_query': community_query,
            'community_address': community_query,
            'community_coordinate': community_coordinate,
            'workplace_address': workplace_query,
            'workplace_coordinate': workplace_coordinate,
            'driving_duration_sec': int(driving.get('duration') or 0),
            'driving_distance_meter': int(driving.get('distance') or 0),
            'transit_duration_sec': int(best_transit.get('duration') or 0),
            'transit_distance_meter': int(best_transit.get('distance') or 0),
            'transit_walking_distance_meter': _sum_transit_walking_distance(best_transit),
            'transit_route': json.dumps(best_transit, ensure_ascii=False),
            'created_at': now if not existing else existing['CREATED_AT'],
            'updated_at': now,
        }

        self.db.upsertCommunityCommute(record)
        return record

    def _row_to_commute_record(self, row):
        return {
            'region': row['REGION'],
            'location': row['LOCATION'],
            'workplace_code': row['WORKPLACE_CODE'],
            'workplace_name': row['WORKPLACE_NAME'],
            'route_provider': row['ROUTE_PROVIDER'],
            'reference_rule': row['REFERENCE_RULE'],
            'reference_departure_at': row['REFERENCE_DEPARTURE_AT'],
            'community_query': row['COMMUNITY_QUERY'],
            'community_address': row['COMMUNITY_ADDRESS'],
            'community_coordinate': row['COMMUNITY_COORDINATE'],
            'workplace_address': row['WORKPLACE_ADDRESS'],
            'workplace_coordinate': row['WORKPLACE_COORDINATE'],
            'driving_duration_sec': row['DRIVING_DURATION_SEC'],
            'driving_distance_meter': row['DRIVING_DISTANCE_METER'],
            'transit_duration_sec': row['TRANSIT_DURATION_SEC'],
            'transit_distance_meter': row['TRANSIT_DISTANCE_METER'],
            'transit_walking_distance_meter': row['TRANSIT_WALKING_DISTANCE_METER'],
            'transit_route': row['TRANSIT_ROUTE'],
        }


def _sum_transit_walking_distance(route: dict) -> int:
    total = 0
    for step in route.get('steps') or []:
        for scheme in step.get('schemes') or []:
            if scheme.get('type') == 5:
                total += int(scheme.get('distance') or 0)
    return total
