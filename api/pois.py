import os
import json
import math
import requests
from http.server import BaseHTTPRequestHandler
from openai import OpenAI

DASHSCOPE_API_KEY = os.environ.get('DASHSCOPE_API_KEY', '')
BAIDU_MAP_AK = os.environ.get('BAIDU_MAP_AK', '')

qwen_client = OpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)


def wgs84_to_bd09(lng, lat):
    x_pi = 3.14159265358979324 * 3000.0 / 180.0
    pi = 3.1415926535897932384626
    a = 6378245.0
    ee = 0.00669342162296594323
    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlng = _transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * pi
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * pi)
    dlng = (dlng * 180.0) / (a / sqrtmagic * math.cos(radlat) * pi)
    mglat = lat + dlat
    mglng = lng + dlng
    z = math.sqrt(mglng * mglng + mglat * mglat) + 0.00002 * math.sin(mglat * x_pi)
    theta = math.atan2(mglat, mglng) + 0.000003 * math.cos(mglng * x_pi)
    return z * math.cos(theta) + 0.0065, z * math.sin(theta) + 0.006


def bd09_to_wgs84(bd_lng, bd_lat):
    x_pi = 3.14159265358979324 * 3000.0 / 180.0
    pi = 3.1415926535897932384626
    a = 6378245.0
    ee = 0.00669342162296594323
    x = bd_lng - 0.0065
    y = bd_lat - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * x_pi)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * x_pi)
    gg_lng = z * math.cos(theta)
    gg_lat = z * math.sin(theta)
    dlat = _transform_lat(gg_lng - 105.0, gg_lat - 35.0)
    dlng = _transform_lng(gg_lng - 105.0, gg_lat - 35.0)
    radlat = gg_lat / 180.0 * pi
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * pi)
    dlng = (dlng * 180.0) / (a / sqrtmagic * math.cos(radlat) * pi)
    return gg_lng - dlng, gg_lat - dlat


def _transform_lat(lng, lat):
    pi = 3.1415926535897932384626
    ret = -100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat + \
          0.1 * lng * lat + 0.2 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * pi) + 20.0 * math.sin(2.0 * lng * pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lat * pi) + 40.0 * math.sin(lat / 3.0 * pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(lat / 12.0 * pi) + 320 * math.sin(lat * pi / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lng(lng, lat):
    pi = 3.1415926535897932384626
    ret = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng + \
          0.1 * lng * lat + 0.1 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * pi) + 20.0 * math.sin(2.0 * lng * pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lng * pi) + 40.0 * math.sin(lng / 3.0 * pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(lng / 12.0 * pi) + 300.0 * math.sin(lng / 30.0 * pi)) * 2.0 / 3.0
    return ret


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(content_length))

        lat = body.get('lat', 0)
        lng = body.get('lng', 0)
        radius = body.get('radius', 300)

        if not lat or not lng:
            self._respond(400, {"error": "未提供位置"})
            return

        bd_lng, bd_lat = wgs84_to_bd09(lng, lat)
        url = "https://api.map.baidu.com/place/v2/search"
        params = {
            "query": "景点|商场|餐厅|酒店|学校|医院|公园|地标|写字楼|银行|超市|便利店",
            "location": f"{bd_lat},{bd_lng}",
            "radius": radius,
            "output": "json",
            "ak": BAIDU_MAP_AK,
            "scope": 2,
            "page_size": 20,
        }

        try:
            resp = requests.get(url, params=params, timeout=5)
            data = resp.json()
            pois = []
            if data.get("status") == 0:
                for item in data.get("results", []):
                    poi_bd_lat = item.get("location", {}).get("lat", 0)
                    poi_bd_lng = item.get("location", {}).get("lng", 0)
                    if not poi_bd_lat or not poi_bd_lng:
                        continue
                    poi_wgs_lng, poi_wgs_lat = bd09_to_wgs84(poi_bd_lng, poi_bd_lat)
                    pois.append({
                        "name": item.get("name", ""),
                        "type": item.get("detail_info", {}).get("type", item.get("tag", "")),
                        "address": item.get("address", ""),
                        "lat": poi_wgs_lat,
                        "lng": poi_wgs_lng,
                    })
            self._respond(200, {"pois": pois})
        except Exception as e:
            self._respond(500, {"error": str(e)[:100]})

    def _respond(self, status, data):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
