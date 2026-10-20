"""本地双根 HTTP 服务：/ 伺服仓库根（index.html），/input/ 伺服输入文件夹。"""
from __future__ import annotations

import os
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

_servers = []


class _DualRootHandler(SimpleHTTPRequestHandler):
    repo_root = '.'
    input_root = '.'

    def log_message(self, *args):   # 静音访问日志
        pass

    def translate_path(self, path):
        path = unquote(path.split('?', 1)[0].split('#', 1)[0])
        if path.startswith('/input/'):
            rel = path[len('/input/'):]
            base = self.input_root
        elif path == '/input':
            base = self.input_root
            rel = ''
        else:
            rel = path.lstrip('/')
            base = self.repo_root
        target = os.path.realpath(os.path.join(base, rel))
        root = os.path.realpath(base)
        if target != root and not target.startswith(root + os.sep):
            self.send_error(404)
            return os.devnull
        return target


def serve(repo_root: str, input_root: str) -> str:
    """起服务（127.0.0.1 随机端口、daemon 线程），返回 base URL。"""
    handler = type('BoundHandler', (_DualRootHandler,), {'repo_root': os.path.abspath(repo_root),
                                                         'input_root': os.path.abspath(input_root)})
    httpd = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    httpd.daemon_threads = True
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    _servers.append(httpd)
    return f'http://127.0.0.1:{httpd.server_address[1]}'


def shutdown():
    for s in _servers:
        s.shutdown()
    _servers.clear()
