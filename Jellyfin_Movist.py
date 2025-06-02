from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import subprocess
import urllib.parse

# 配置
HOST = "localhost"  # 本地监听地址
PORT = 58001       # 必须和用户脚本中的端口一致
MOVIST_PRO_PATH = "/Applications/Movist Pro.app/Contents/MacOS/Movist Pro"  # Movist Pro 路径
API_KEY = "替换为你的实际 API Key"

class RequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        # 只处理 /embyToLocalPlayer/ 路径
        if not self.path.startswith("/embyToLocalPlayer/"):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")
            return

        # 解析 JSON 数据
        content_length = int(self.headers["Content-Length"])
        post_data = self.rfile.read(content_length)
        try:
            data = json.loads(post_data.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Invalid JSON")
            return

        # 提取 playbackUrl
        playback_url = data.get("playbackUrl")
        if not playback_url:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Missing 'playbackUrl' in request")
            return

        # 修改 playback_url：替换 PlaybackInfo 之后的内容
        if "PlaybackInfo" in playback_url:
            # 分割 URL，保留 PlaybackInfo 之前的部分
            base_url = playback_url.split("PlaybackInfo")[0]
            # 构造新的 Download URL
            modified_url = f"{base_url}Download?api_key={API_KEY}"
        else:
            # 如果 URL 中没有 PlaybackInfo，直接使用原 URL（可选：也可以返回错误）
            modified_url = playback_url

        # 调用 Movist Pro 播放修改后的 URL
        try:
            subprocess.run([
                "open", "-a", MOVIST_PRO_PATH, modified_url
            ], check=True)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Playback started with Movist Pro")
        except subprocess.CalledProcessError as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Failed to play: {str(e)}".encode("utf-8"))

if __name__ == "__main__":
    server = HTTPServer((HOST, PORT), RequestHandler)
    print(f"Server running on http://{HOST}:{PORT} (Press Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
        print("Server stopped")
