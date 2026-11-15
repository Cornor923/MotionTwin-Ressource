"""Sert la page en local sans cache navigateur (le catalogue change à chaque reconstruction).

usage : python tools/serve.py [port]   puis http://127.0.0.1:8642/
"""
import functools, http.server, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class NoCache(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8642
    handler = functools.partial(NoCache, directory=ROOT)
    print('http://127.0.0.1:%d/' % port, flush=True)
    http.server.ThreadingHTTPServer(('127.0.0.1', port), handler).serve_forever()
