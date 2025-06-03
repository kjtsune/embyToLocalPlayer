from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import subprocess

HOST = "localhost"
PORT = 58000
MOVIST_PRO_PATH = "/Applications/Movist Pro.app/Contents/MacOS/Movist Pro"

class RequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        print(f"\n=== 收到 POST 请求 ===")
        print(f"路径: {self.path}")
        for key, value in self.headers.items():
            print(f"  {key}: {value}")

        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)
        print(f"\n原始数据内容:\n{post_data.decode('utf-8', errors='ignore')}")

        # 只处理指定路径
        if not self.path.startswith("/embyToLocalPlayer/"):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")
            return

        try:
            data = json.loads(post_data.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Invalid JSON")
            return

        # 从嵌套结构中提取播放服务器、token、UserId（用于构造 URL）
        try:
            server_address = data["ApiClient"]["_serverInfo"]["ManualAddress"]
            access_token = data["ApiClient"]["_serverInfo"]["AccessToken"]
            user_id = data["ApiClient"]["_serverInfo"]["UserId"]
        except KeyError as e:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(f"Missing required field: {e}".encode("utf-8"))
            return

        # 从 playbackData 中获取 item_id
        try:
            item_id = data["playbackData"]["MediaSources"][0]["Id"]
        except (KeyError, IndexError, TypeError) as e:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Missing or invalid playbackData.MediaSources.Id")
            return

        modified_url = f"{server_address}/Items/{item_id}/Download?api_key={access_token}"

        print(f"\n最终播放 URL: {modified_url}")

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
