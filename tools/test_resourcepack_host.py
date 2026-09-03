import importlib.util
import os
import tempfile
import threading
import unittest
import urllib.request
from http.server import HTTPServer
from pathlib import Path

HOST_SCRIPT = Path(__file__).resolve().parents[2] / "Divine_Journey_2.23.4_Server_Pack" / "resourcepack-host.py"


class ResourcePackHostTests(unittest.TestCase):
    def test_atomic_pack_replacement_is_visible_without_stale_length(self):
        spec = importlib.util.spec_from_file_location("resourcepack_host", HOST_SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as td:
            pack = Path(td) / "pack.zip"
            pack.write_bytes(b"old")
            handler, _ = module.build_handler(str(pack), pack.name)
            server = HTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            url = f"http://127.0.0.1:{server.server_port}/{pack.name}"
            try:
                with urllib.request.urlopen(url, timeout=5) as response:
                    self.assertEqual(response.read(), b"old")
                replacement = Path(td) / "replacement.zip"
                replacement.write_bytes(b"new-artifact-is-larger")
                os.replace(replacement, pack)
                with urllib.request.urlopen(url, timeout=5) as response:
                    self.assertEqual(response.read(), b"new-artifact-is-larger")
                    self.assertEqual(response.headers["Content-Length"], str(len(b"new-artifact-is-larger")))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
