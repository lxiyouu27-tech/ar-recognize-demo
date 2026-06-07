import os
import json
from http.server import BaseHTTPRequestHandler
from openai import OpenAI

DASHSCOPE_API_KEY = os.environ.get('DASHSCOPE_API_KEY', '')

qwen_client = OpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(content_length))

        image_base64 = body.get('image', '')
        lat = body.get('lat', 0)
        lng = body.get('lng', 0)
        heading = body.get('heading', 0)
        visible_pois = body.get('visible_pois', [])

        if not image_base64:
            self._respond(400, {"error": "未提供图片"})
            return

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
            self._respond(200, {"results": results})
        except json.JSONDecodeError:
            self._respond(200, {"results": [], "raw": result_text[:200]})
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
