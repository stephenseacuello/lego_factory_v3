#!/usr/bin/env python3
"""
Webcam MJPEG Streaming Server
Streams webcam video over HTTP for Docker container access.

Usage:
    python webcam_stream.py [camera_index] [port]

    camera_index: 0=FaceTime, 1=Logitech C920e (default), 2=iPhone
    port: HTTP port (default 8081)

Access stream at: http://host.docker.internal:8081/video
"""

import cv2
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import threading

# Configuration
CAMERA_INDEX = int(sys.argv[1]) if len(sys.argv) > 1 else 1  # Default: Logitech C920e
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8081
# Use lower resolution for less lag (640x480 instead of 1280x720)
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
JPEG_QUALITY = 60  # Lower quality = faster transfer

class CameraCapture:
    """Thread-safe camera capture."""

    def __init__(self, camera_index):
        self.cap = cv2.VideoCapture(camera_index)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        self.lock = threading.Lock()
        self.frame = None
        self.running = True

        # Start capture thread
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()

    def _capture_loop(self):
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                with self.lock:
                    self.frame = frame

    def get_frame(self):
        with self.lock:
            if self.frame is not None:
                return self.frame.copy()
        return None

    def get_jpeg(self):
        frame = self.get_frame()
        if frame is not None:
            _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
            return jpeg.tobytes()
        return None

    def release(self):
        self.running = False
        self.cap.release()


class StreamHandler(BaseHTTPRequestHandler):
    """HTTP request handler for MJPEG stream."""

    camera = None

    def do_GET(self):
        import time
        if self.path == '/video' or self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=frame')
            self.end_headers()

            try:
                while True:
                    jpeg = self.camera.get_jpeg()
                    if jpeg:
                        self.wfile.write(b'--frame\r\n')
                        self.wfile.write(b'Content-Type: image/jpeg\r\n\r\n')
                        self.wfile.write(jpeg)
                        self.wfile.write(b'\r\n')
                    # Limit to ~15 FPS to reduce CPU/bandwidth
                    time.sleep(0.066)
            except (BrokenPipeError, ConnectionResetError):
                pass

        elif self.path == '/frame':
            # Single frame endpoint
            jpeg = self.camera.get_jpeg()
            if jpeg:
                self.send_response(200)
                self.send_header('Content-type', 'image/jpeg')
                self.send_header('Content-length', str(len(jpeg)))
                self.end_headers()
                self.wfile.write(jpeg)
            else:
                self.send_error(500, 'No frame available')

        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "ok", "camera": "active"}')

        else:
            self.send_error(404, 'Not found')

    def log_message(self, format, *args):
        # Suppress logging for cleaner output
        pass


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in separate threads."""
    allow_reuse_address = True
    daemon_threads = True


def main():
    print(f"=" * 50)
    print(f"LEGO MCP Webcam Streaming Server")
    print(f"=" * 50)
    print(f"Camera Index: {CAMERA_INDEX}")
    print(f"Resolution: {FRAME_WIDTH}x{FRAME_HEIGHT}")
    print(f"Port: {PORT}")
    print()

    # Initialize camera
    print("Initializing camera...")
    camera = CameraCapture(CAMERA_INDEX)

    # Wait for first frame
    import time
    for _ in range(30):
        if camera.get_frame() is not None:
            break
        time.sleep(0.1)

    if camera.get_frame() is None:
        print("ERROR: Could not capture from camera!")
        print("Try a different camera index (0, 1, 2...)")
        return

    print("Camera ready!")
    print()

    # Set camera for handler
    StreamHandler.camera = camera

    # Start server
    server = ThreadedHTTPServer(('0.0.0.0', PORT), StreamHandler)

    print(f"Stream URLs:")
    print(f"  Local:  http://localhost:{PORT}/video")
    print(f"  Docker: http://host.docker.internal:{PORT}/video")
    print()
    print("Press Ctrl+C to stop")
    print("-" * 50)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        camera.release()
        server.shutdown()


if __name__ == '__main__':
    main()
