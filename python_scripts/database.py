#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库访问层。
"""

import re
import sqlite3
import sys
from typing import Dict, List, Optional, Tuple


BASE_HOUSE_COLUMNS = [
    "ID",
    "LOCATION",
    "TYPE",
    "SIZE",
    "TOWARDS",
    "FLOOD",
    "YEAR",
    "BUILDING",
    "TOTAL_PRICE",
    "UNIT_PRICE",
    "DATE_PRICE",
    "REGION",
]


BASE_SELLOUT_COLUMNS = BASE_HOUSE_COLUMNS[:11] + ["DATE", "REGION"]


class Database:
    def __init__(self, db_path=None, workplaces: Optional[List[Dict]] = None):
        if db_path is None:
            db_path = sys.path[0] + '/../db/lianjia.db'

        self.workplaces = self._normalize_workplaces(workplaces or [])
        self.commute_column_meta = self._build_commute_column_meta()

        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.c = self.conn.cursor()

        self.__createHouseTable()
        self.__createSellOutTable()
        self.__createCommunityCommuteTable()
        self.__ensureDynamicSchema()
        self.conn.commit()

    def __del__(self):
        try:
            self.conn.commit()
            self.conn.close()
        except Exception:
            pass

    def _normalize_workplaces(self, workplaces: List[Dict]) -> List[Dict]:
        normalized = []
        seen_codes = set()

        for workplace in workplaces:
            code = str(workplace.get('code', '')).strip().lower()
            if not code or not re.match(r'^[a-z][a-z0-9_]*$', code):
                raise ValueError(f"非法 workplace code: {workplace.get('code')}")
            if code in seen_codes:
                raise ValueError(f"重复 workplace code: {code}")

            seen_codes.add(code)
            normalized.append({
                'code': code,
                'name': workplace.get('name', code),
                'address': workplace['address'],
            })

        return normalized

    def _build_commute_column_meta(self) -> List[Dict]:
        meta = []
        for workplace in self.workplaces:
            code = workplace['code']
            meta.append({
                'house_key': f'commute_{code}_driving_duration',
                'column': f'COMMUTE_{code.upper()}_DRIVING_DURATION',
            })
            meta.append({
                'house_key': f'commute_{code}_transit_duration',
                'column': f'COMMUTE_{code.upper()}_TRANSIT_DURATION',
            })
        return meta

    def _get_table_columns(self, table_name: str) -> Dict[str, sqlite3.Row]:
        result = self.c.execute(f"PRAGMA table_info({table_name})").fetchall()
        return {row['name']: row for row in result}

    def _ensure_columns(self, table_name: str, column_defs: List[Tuple[str, str]]):
        existing = self._get_table_columns(table_name)
        for column_name, column_type in column_defs:
            if column_name not in existing:
                self.c.execute(
                    f'ALTER TABLE {table_name} ADD COLUMN "{column_name}" {column_type}'
                )

    def _build_house_values(self, house: Dict) -> Tuple[List[str], List]:
        columns = list(BASE_HOUSE_COLUMNS)
        values = [
            house['house_id'],
            house['house_location'],
            house['house_type'],
            house['house_size'],
            house['house_towards'],
            house['house_flood'],
            house['house_year'],
            house['house_building'],
            house['house_total_price'],
            house['house_unit_price'],
            house['house_date_price'],
            house['house_region'],
        ]

        for item in self.commute_column_meta:
            columns.append(item['column'])
            values.append(house.get(item['house_key']))

        return columns, values

    def _build_sellout_values(self, house: Dict) -> Tuple[List[str], List]:
        columns = list(BASE_SELLOUT_COLUMNS)
        values = [
            house['house_id'],
            house['house_location'],
            house['house_type'],
            house['house_size'],
            house['house_towards'],
            house['house_flood'],
            house['house_year'],
            house['house_building'],
            house['house_total_price'],
            house['house_unit_price'],
            house['house_date_price'],
            house['date'],
            house['house_region'],
        ]

        for item in self.commute_column_meta:
            columns.append(item['column'])
            values.append(house.get(item['house_key']))

        return columns, values

    def __createHouseTable(self):
        self.c.execute('''
        CREATE TABLE IF NOT EXISTS HOUSE (
            ID             INT      PRIMARY KEY     NOT NULL,
            LOCATION       TEXT                     NOT NULL,
            TYPE           TEXT                     NOT NULL,
            SIZE           TEXT                     NOT NULL,
            TOWARDS        TEXT                     NOT NULL,
            FLOOD          TEXT                     NOT NULL,
            YEAR           TEXT                     NOT NULL,
            BUILDING       TEXT                     NOT NULL,
            TOTAL_PRICE    TEXT                     NOT NULL,
            UNIT_PRICE     TEXT                     NOT NULL,
            DATE_PRICE     TEXT                     NOT NULL,
            REGION         TEXT                     NOT NULL,
            QUOTEDATE      TEXT,
            LASTTRADEDATE  TEXT,
            VIEWNUM        INT,
            FOLLOWNUM      INT
        );
        ''')

    def __createSellOutTable(self):
        self.c.execute('''
        CREATE TABLE IF NOT EXISTS SELLOUT (
            ID             INT      PRIMARY KEY     NOT NULL,
            LOCATION       TEXT                     NOT NULL,
            TYPE           TEXT                     NOT NULL,
            SIZE           TEXT                     NOT NULL,
            TOWARDS        TEXT                     NOT NULL,
            FLOOD          TEXT                     NOT NULL,
            YEAR           TEXT                     NOT NULL,
            BUILDING       TEXT                     NOT NULL,
            TOTAL_PRICE    TEXT                     NOT NULL,
            UNIT_PRICE     TEXT                     NOT NULL,
            DATE_PRICE     TEXT                     NOT NULL,
            DATE           TEXT                     NOT NULL,
            REGION         TEXT                     NOT NULL,
            QUOTEDATE      TEXT,
            LASTTRADEDATE  TEXT,
            VIEWNUM        INT,
            FOLLOWNUM      INT
        );
        ''')

    def __createCommunityCommuteTable(self):
        self.c.execute('''
        CREATE TABLE IF NOT EXISTS COMMUNITY_COMMUTE (
            ID                            INTEGER PRIMARY KEY AUTOINCREMENT,
            REGION                        TEXT NOT NULL,
            LOCATION                      TEXT NOT NULL,
            WORKPLACE_CODE                TEXT NOT NULL,
            WORKPLACE_NAME                TEXT NOT NULL,
            ROUTE_PROVIDER                TEXT,
            REFERENCE_RULE                TEXT,
            REFERENCE_DEPARTURE_AT        TEXT,
            COMMUNITY_QUERY               TEXT NOT NULL,
            COMMUNITY_ADDRESS             TEXT,
            COMMUNITY_COORDINATE          TEXT,
            WORKPLACE_ADDRESS             TEXT NOT NULL,
            WORKPLACE_COORDINATE          TEXT,
            DRIVING_DURATION_SEC          INT,
            DRIVING_DISTANCE_METER        INT,
            TRANSIT_DURATION_SEC          INT,
            TRANSIT_DISTANCE_METER        INT,
            TRANSIT_WALKING_DISTANCE_METER INT,
            TRANSIT_ROUTE                 TEXT,
            CREATED_AT                    TEXT NOT NULL,
            UPDATED_AT                    TEXT NOT NULL,
            UNIQUE(REGION, LOCATION, WORKPLACE_CODE)
        );
        ''')

    def __ensureDynamicSchema(self):
        commute_columns = [
            (item['column'], 'INT') for item in self.commute_column_meta
        ]
        self._ensure_columns('HOUSE', commute_columns)
        self._ensure_columns('SELLOUT', commute_columns)
        self._ensure_columns(
            'COMMUNITY_COMMUTE',
            [
                ('ROUTE_PROVIDER', 'TEXT'),
                ('REFERENCE_RULE', 'TEXT'),
                ('REFERENCE_DEPARTURE_AT', 'TEXT'),
            ]
        )

    def insertHouse(self, house):
        columns, values = self._build_house_values(house)
        placeholders = ', '.join(['?'] * len(columns))
        sql = (
            f"INSERT INTO HOUSE ({', '.join(columns)}) "
            f"VALUES ({placeholders})"
        )
        self.c.execute(sql, values)

    def updateHouse(self, house):
        assignments = [
            "TOTAL_PRICE=?",
            "UNIT_PRICE=?",
            "DATE_PRICE=?",
        ]
        values = [
            house['house_total_price'],
            house['house_unit_price'],
            house['house_date_price'],
        ]

        for item in self.commute_column_meta:
            assignments.append(f"{item['column']}=?")
            values.append(house.get(item['house_key']))

        values.append(house['house_id'])
        sql = f"UPDATE HOUSE SET {', '.join(assignments)} WHERE ID=?"
        self.c.execute(sql, values)

    def selectHouse(self, house_id):
        return self.c.execute("SELECT * FROM HOUSE WHERE ID=?", (house_id,))

    def deleteHouse(self, house_id):
        self.c.execute("DELETE FROM HOUSE WHERE ID=?", (house_id,))

    def countHouse(self):
        return self.c.execute('SELECT count() FROM HOUSE').fetchone()[0]

    def findAllSellOutFromHouse(self, date):
        return self.c.execute(
            "SELECT * FROM HOUSE WHERE DATE_PRICE NOT LIKE ?",
            ('%' + date + '%',)
        )

    def insertSellOut(self, house):
        columns, values = self._build_sellout_values(house)
        placeholders = ', '.join(['?'] * len(columns))
        sql = (
            f"INSERT INTO SELLOUT ({', '.join(columns)}) "
            f"VALUES ({placeholders})"
        )
        self.c.execute(sql, values)

    def selectSellOut(self, house_id):
        return self.c.execute("SELECT * FROM SELLOUT WHERE ID=?", (house_id,))

    def deleteSellOut(self, house_id):
        self.c.execute("DELETE FROM SELLOUT WHERE ID=?", (house_id,))

    def fetchAllHouses(self):
        return self.c.execute(
            "SELECT ID, LOCATION, TYPE, SIZE, TOWARDS, FLOOD, YEAR, BUILDING, "
            "TOTAL_PRICE, UNIT_PRICE, DATE_PRICE, REGION, QUOTEDATE, LASTTRADEDATE, VIEWNUM, FOLLOWNUM "
            "FROM HOUSE ORDER BY REGION, ID"
        ).fetchall()

    def fetchAllSellOut(self):
        return self.c.execute(
            "SELECT ID, LOCATION, TYPE, SIZE, TOWARDS, FLOOD, YEAR, BUILDING, "
            "TOTAL_PRICE, UNIT_PRICE, DATE_PRICE, DATE, REGION, QUOTEDATE, LASTTRADEDATE, VIEWNUM, FOLLOWNUM "
            "FROM SELLOUT ORDER BY DATE DESC, REGION, ID"
        ).fetchall()

    def fetchDistinctCommunities(self):
        return self.c.execute(
            "SELECT DISTINCT REGION, LOCATION FROM HOUSE ORDER BY REGION, LOCATION"
        ).fetchall()

    def fetchCommunityCommute(self, region: str, location: str, workplace_code: str):
        return self.c.execute(
            "SELECT * FROM COMMUNITY_COMMUTE WHERE REGION=? AND LOCATION=? AND WORKPLACE_CODE=?",
            (region, location, workplace_code)
        ).fetchone()

    def upsertCommunityCommute(self, commute_data: Dict):
        self.c.execute(
            '''
            INSERT INTO COMMUNITY_COMMUTE (
                REGION,
                LOCATION,
                WORKPLACE_CODE,
                WORKPLACE_NAME,
                ROUTE_PROVIDER,
                REFERENCE_RULE,
                REFERENCE_DEPARTURE_AT,
                COMMUNITY_QUERY,
                COMMUNITY_ADDRESS,
                COMMUNITY_COORDINATE,
                WORKPLACE_ADDRESS,
                WORKPLACE_COORDINATE,
                DRIVING_DURATION_SEC,
                DRIVING_DISTANCE_METER,
                TRANSIT_DURATION_SEC,
                TRANSIT_DISTANCE_METER,
                TRANSIT_WALKING_DISTANCE_METER,
                TRANSIT_ROUTE,
                CREATED_AT,
                UPDATED_AT
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(REGION, LOCATION, WORKPLACE_CODE) DO UPDATE SET
                WORKPLACE_NAME=excluded.WORKPLACE_NAME,
                ROUTE_PROVIDER=excluded.ROUTE_PROVIDER,
                REFERENCE_RULE=excluded.REFERENCE_RULE,
                REFERENCE_DEPARTURE_AT=excluded.REFERENCE_DEPARTURE_AT,
                COMMUNITY_QUERY=excluded.COMMUNITY_QUERY,
                COMMUNITY_ADDRESS=excluded.COMMUNITY_ADDRESS,
                COMMUNITY_COORDINATE=excluded.COMMUNITY_COORDINATE,
                WORKPLACE_ADDRESS=excluded.WORKPLACE_ADDRESS,
                WORKPLACE_COORDINATE=excluded.WORKPLACE_COORDINATE,
                DRIVING_DURATION_SEC=excluded.DRIVING_DURATION_SEC,
                DRIVING_DISTANCE_METER=excluded.DRIVING_DISTANCE_METER,
                TRANSIT_DURATION_SEC=excluded.TRANSIT_DURATION_SEC,
                TRANSIT_DISTANCE_METER=excluded.TRANSIT_DISTANCE_METER,
                TRANSIT_WALKING_DISTANCE_METER=excluded.TRANSIT_WALKING_DISTANCE_METER,
                TRANSIT_ROUTE=excluded.TRANSIT_ROUTE,
                UPDATED_AT=excluded.UPDATED_AT
            ''',
            (
                commute_data['region'],
                commute_data['location'],
                commute_data['workplace_code'],
                commute_data['workplace_name'],
                commute_data.get('route_provider'),
                commute_data.get('reference_rule'),
                commute_data.get('reference_departure_at'),
                commute_data['community_query'],
                commute_data.get('community_address'),
                commute_data.get('community_coordinate'),
                commute_data['workplace_address'],
                commute_data.get('workplace_coordinate'),
                commute_data.get('driving_duration_sec'),
                commute_data.get('driving_distance_meter'),
                commute_data.get('transit_duration_sec'),
                commute_data.get('transit_distance_meter'),
                commute_data.get('transit_walking_distance_meter'),
                commute_data.get('transit_route'),
                commute_data['created_at'],
                commute_data['updated_at'],
            )
        )

    def updateHouseCommuteByCommunity(self, region: str, location: str, commute_values: Dict):
        assignments = []
        values = []

        for item in self.commute_column_meta:
            if item['house_key'] in commute_values:
                assignments.append(f"{item['column']}=?")
                values.append(commute_values[item['house_key']])

        if not assignments:
            return

        values.extend([region, location])
        sql = f"UPDATE HOUSE SET {', '.join(assignments)} WHERE REGION=? AND LOCATION=?"
        self.c.execute(sql, values)
