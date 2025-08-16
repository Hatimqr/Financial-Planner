#!/usr/bin/env python3
"""
Simple HTTP server to serve the browser-based frontend tests from the correct origin.
This ensures CORS works properly when testing the frontend integration.
"""

import http.server
import socketserver
import os
import sys
from pathlib import Path

# Port must match the frontend origin configured in CORS
PORT = 5175  # Using 5175 to avoid conflict with actual frontend on 5174

class CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

def serve_tests():
    """Serve the browser-based tests from the backend directory."""
    
    # Change to backend directory to serve files
    backend_dir = Path(__file__).parent
    os.chdir(backend_dir)
    
    with socketserver.TCPServer(("", PORT), CORSRequestHandler) as httpd:
        print(f"🌐 Serving frontend tests at http://localhost:{PORT}")
        print(f"📁 Serving from: {backend_dir}")
        print("📋 Available test files:")
        print(f"   - Browser Test: http://localhost:{PORT}/tests/frontend/test_frontend_browser.html")
        print("🛑 Press Ctrl+C to stop the server")
        print()
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 Server stopped.")

if __name__ == "__main__":
    serve_tests()