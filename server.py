import os
import json
import base64
import math
import requests
from flask import Flask, request, jsonify, send_from_directory
from openai import OpenAI

app = Flask(__name__, static_folder='static')

DASHSCOPE_API_KEY = os.environ.get('DASHSCOPE_API_KEY', '')
BAIDU_MAP_AK = os.environ.get('BAIDU_MAP_AK', '')

qwen_client = OpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)


def wgs84_to_bd09(lng, lat):
    """WGS84坐标(GPS原始) -> BD09坐标(百度地图)"""
    x_pi = 3.14159265358979324 * 3000.0 / 180.0
    pi = 3.1415926535897932384626
    a = 6378245.0
    ee = 0.00669342162296594323

    # WGS84 -> GCJ02
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

    # GCJ02 -> BD09
    z = math.sqrt(mglng * mglng + mglat * mglat) + 0.00002 * math.sin(mglat * x_pi)
    theta = math.atan2(mglat, mglng) + 0.000003 * math.cos(mglng * x_pi)
    bd_lng = z * math.cos(theta) + 0.0065
    bd_lat = z * math.sin(theta) + 0.006
    return bd_lng, bd_lat


def _transform_lat(lng, lat):
    pi = 3.1415926535897932384626
    ret = -100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat + \
          0.1 * lng * lat + 0.2 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * pi) + 20.0 *
            math.sin(2.0 * lng * pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lat * pi) + 40.0 *
            math.sin(lat / 3.0 * pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(lat / 12.0 * pi) + 320 *
            math.sin(lat * pi / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lng(lng, lat):
    pi = 3.1415926535897932384626
    ret = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng + \
          0.1 * lng * lat + 0.1 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * pi) + 20.0 *
            math.sin(2.0 * lng * pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lng * pi) + 40.0 *
            math.sin(lng / 3.0 * pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(lng / 12.0 * pi) + 300.0 *
            math.sin(lng / 30.0 * pi)) * 2.0 / 3.0
    return ret


def bd09_to_wgs84(bd_lng, bd_lat):
    """BD09坐标(百度地图) -> WGS84坐标(GPS)"""
    x_pi = 3.14159265358979324 * 3000.0 / 180.0
    pi = 3.1415926535897932384626
    a = 6378245.0
    ee = 0.00669342162296594323

    # BD09 -> GCJ02
    x = bd_lng - 0.0065
    y = bd_lat - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * x_pi)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * x_pi)
    gg_lng = z * math.cos(theta)
    gg_lat = z * math.sin(theta)

    # GCJ02 -> WGS84
    dlat = _transform_lat(gg_lng - 105.0, gg_lat - 35.0)
    dlng = _transform_lng(gg_lng - 105.0, gg_lat - 35.0)
    radlat = gg_lat / 180.0 * pi
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * pi)
    dlng = (dlng * 180.0) / (a / sqrtmagic * math.cos(radlat) * pi)
    wgs_lat = gg_lat - dlat
    wgs_lng = gg_lng - dlng
    return wgs_lng, wgs_lat


def search_nearby_pois(lat, lng, radius=200):
    """调用百度地图地点检索API获取周边POI"""
    bd_lng, bd_lat = wgs84_to_bd09(lng, lat)

    url = "https://api.map.baidu.com/place/v2/search"
    params = {
        "query": "景点|商场|餐厅|酒店|学校|医院|公园|地标|写字楼|银行",
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
        if data.get("status") == 0:
            pois = []
            for item in data.get("results", []):
                poi = {
                    "name": item.get("name", ""),
                    "type": item.get("detail_info", {}).get("type", item.get("tag", "")),
                    "address": item.get("address", ""),
                    "distance": item.get("detail_info", {}).get("distance", ""),
                }
                pois.append(poi)
            return pois
        return []
    except Exception:
        return []


def search_nearby_pois_with_location(lat, lng, radius=300):
    """调用百度地图API获取周边POI（含坐标，用于AR投射）"""
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
        if data.get("status") == 0:
            pois = []
            for item in data.get("results", []):
                poi_bd_lat = item.get("location", {}).get("lat", 0)
                poi_bd_lng = item.get("location", {}).get("lng", 0)
                if not poi_bd_lat or not poi_bd_lng:
                    continue
                poi_wgs_lng, poi_wgs_lat = bd09_to_wgs84(poi_bd_lng, poi_bd_lat)
                poi = {
                    "name": item.get("name", ""),
                    "type": item.get("detail_info", {}).get("type", item.get("tag", "")),
                    "address": item.get("address", ""),
                    "lat": poi_wgs_lat,
                    "lng": poi_wgs_lng,
                }
                pois.append(poi)
            return pois
        return []
    except Exception:
        return []


def recognize_with_qwen(image_base64, lat, lng, pois):
    """调用通义千问Qwen-VL进行图片识别"""
    poi_text = "\n".join([
        f"- {p['name']}（{p['type']}）{p['address']} 距离{p['distance']}米"
        for p in pois
    ]) if pois else "（未获取到周边POI信息）"

    prompt = f"""你是一个AR场景识别助手。用户用手机拍摄了一张周围环境的照片。
当前GPS位置：纬度{lat}, 经度{lng}
附近200米内的地点(POI)列表：
{poi_text}

请根据照片内容，结合位置信息和附近POI列表，识别画面中可能出现的建筑、店铺、景点或地标。
要求：
1. 仔细观察照片中的建筑外观、招牌文字、环境特征
2. 将视觉观察与POI列表进行匹配
3. 如果照片中的内容不在POI列表中，也可以根据视觉信息给出判断

请严格返回以下JSON格式（不要包含其他文字）：
[{{"name": "名称", "type": "类型(如:景点/餐厅/商场/学校/公园等)", "confidence": "高/中/低", "description": "50字以内的简介"}}]

如果画面中没有可识别的地标或建筑，返回：[]"""

    try:
        response = qwen_client.chat.completions.create(
            model="qwen-vl-plus",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
                    {"type": "text", "text": prompt}
                ]
            }],
            temperature=0.3,
        )
        result_text = response.choices[0].message.content.strip()
        # 尝试提取JSON
        if result_text.startswith("```"):
            lines = result_text.split("\n")
            result_text = "\n".join(lines[1:-1])
        return json.loads(result_text)
    except json.JSONDecodeError:
        return [{"name": "识别结果", "type": "未知", "confidence": "低", "description": result_text[:100]}]
    except Exception as e:
        return [{"name": "识别失败", "type": "错误", "confidence": "低", "description": str(e)[:100]}]


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/ar')
def ar_page():
    return send_from_directory('static', 'ar.html')


@app.route('/api/pois', methods=['POST'])
def get_pois():
    """获取周边POI（含WGS84坐标，用于AR投射）"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "无效请求"}), 400

    lat = data.get('lat', 0)
    lng = data.get('lng', 0)
    radius = data.get('radius', 300)

    if not lat or not lng:
        return jsonify({"error": "未提供位置"}), 400

    pois = search_nearby_pois_with_location(lat, lng, radius)
    return jsonify({"pois": pois})


@app.route('/api/recognize-frame', methods=['POST'])
def recognize_frame():
    """AR模式下的截帧识别（用于增强POI信息）"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "无效请求"}), 400

    image_base64 = data.get('image', '')
    lat = data.get('lat', 0)
    lng = data.get('lng', 0)
    heading = data.get('heading', 0)
    visible_pois = data.get('visible_pois', [])

    if not image_base64:
        return jsonify({"error": "未提供图片"}), 400

    if ',' in image_base64:
        image_base64 = image_base64.split(',', 1)[1]

    poi_text = "\n".join([f"- {p}" for p in visible_pois]) if visible_pois else "无"

    prompt = f"""你是AR场景识别助手。用户手机摄像头正对着前方拍摄。
当前GPS位置：纬度{lat}, 经度{lng}，朝向{heading}°
当前视野内根据方位计算可能出现的POI：
{poi_text}

请观察照片，告诉我：
1. 画面中能看到哪些建筑/店铺/地标？
2. 与上面列出的POI是否匹配？

返回JSON格式（不要其他文字）：
[{{"name": "名称", "type": "类型", "confirmed": true/false, "description": "20字简介"}}]
confirmed=true表示你确认画面中看到了该地点。"""

    try:
        response = qwen_client.chat.completions.create(
            model="qwen-vl-plus",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
                    {"type": "text", "text": prompt}
                ]
            }],
            temperature=0.3,
        )
        result_text = response.choices[0].message.content.strip()
        if result_text.startswith("```"):
            lines = result_text.split("\n")
            result_text = "\n".join(lines[1:-1])
        results = json.loads(result_text)
        return jsonify({"results": results})
    except json.JSONDecodeError:
        return jsonify({"results": [], "raw": result_text[:200]})
    except Exception as e:
        return jsonify({"error": str(e)[:100]}), 500


@app.route('/api/recognize', methods=['POST'])
def recognize():
    data = request.get_json()
    if not data:
        return jsonify({"error": "无效请求"}), 400

    image_base64 = data.get('image', '')
    lat = data.get('lat', 0)
    lng = data.get('lng', 0)

    if not image_base64:
        return jsonify({"error": "未提供图片"}), 400

    # 去掉data:image/xxx;base64,前缀
    if ',' in image_base64:
        image_base64 = image_base64.split(',', 1)[1]

    pois = search_nearby_pois(lat, lng) if lat and lng else []
    results = recognize_with_qwen(image_base64, lat, lng, pois)

    return jsonify({
        "results": results,
        "pois_found": len(pois),
        "location": {"lat": lat, "lng": lng}
    })


if __name__ == '__main__':
    if not DASHSCOPE_API_KEY:
        print("WARNING: DASHSCOPE_API_KEY not set")
    if not BAIDU_MAP_AK:
        print("WARNING: BAIDU_MAP_AK not set")

    print("Server starting on https://0.0.0.0:8080")
    print("Mobile access: https://<your-ip>:8080/ar")
    app.run(host='0.0.0.0', port=8080, debug=True, ssl_context=('cert.pem', 'key.pem'))
