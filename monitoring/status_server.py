#!/usr/bin/env python3
"""
Simple HTTP server for ZGDK status dashboard
"""

import http.server
import socketserver
import os
import json
from pathlib import Path

class StatusHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="monitoring", **kwargs)
    
    def do_GET(self):
        if self.path == '/api/status':
            self.send_json_status()
        elif self.path == '/' or self.path == '/status':
            self.path = '/status.html'
            super().do_GET()
        else:
            super().do_GET()
    
    def send_json_status(self):
        """Send status.json as API response"""
        try:
            status_file = Path("monitoring/status.json")
            if status_file.exists():
                with open(status_file, 'r') as f:
                    data = json.load(f)
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(data, indent=2).encode())
            else:
                self.send_error(404, "Status data not found")
        except Exception as e:
            self.send_error(500, f"Internal error: {str(e)}")

def run_server(port=8888):
    """Run the status server"""
    os.chdir(Path(__file__).parent.parent)  # Change to project root
    
    with socketserver.TCPServer(("", port), StatusHandler) as httpd:
        print(f"Status dashboard running at http://localhost:{port}")
        print(f"API endpoint: http://localhost:{port}/api/status")
        print("Press Ctrl+C to stop")
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped")

if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8888
    run_server(port)