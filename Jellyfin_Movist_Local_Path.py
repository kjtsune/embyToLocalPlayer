from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import subprocess

HOST = "localhost"
PORT = 58000
MOVIST_PRO_PATH = "/Applications/Movist Pro.app/Contents/MacOS/Movist Pro"

# 路径替换关系：
# "Jellyfin 中的媒体库文件夹": "本机的媒体库文件夹"

PATH_REPLACEMENTS = {
    "/NAS": "/Volumes/share"
}

class RequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if not self.path.startswith("/embyToLocalPlayer/"):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")
            return

        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)

        try:
            data = json.loads(post_data.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Invalid JSON")
            return

        try:
            server_address = data["ApiClient"]["_serverInfo"]["ManualAddress"]
            access_token = data["ApiClient"]["_serverInfo"]["AccessToken"]
            user_id = data["ApiClient"]["_serverInfo"]["UserId"]
        except KeyError as e:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(f"Missing required field: {e}".encode("utf-8"))
            return

        try:
            media_source = data["playbackData"]["MediaSources"][0]
            item_id = media_source["Id"]
            file_path = media_source["Path"]
        except (KeyError, IndexError, TypeError):
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Missing or invalid playbackData.MediaSources")
            return

        replaced_path = file_path
        for old_prefix, new_prefix in PATH_REPLACEMENTS.items():
            if replaced_path.startswith(old_prefix):
                replaced_path = replaced_path.replace(old_prefix, new_prefix, 1)
                break

        try:
            subprocess.run([
                "open", "-a", MOVIST_PRO_PATH, replaced_path
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
