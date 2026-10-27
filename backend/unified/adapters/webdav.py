import asyncio
from urllib.parse import quote, urlsplit
import httpx
from .contracts import Descriptor, AdapterError

MAX_DOWNLOAD_BYTES = 101 * 1024 * 1024


class WebDAVStorage:
    descriptor = Descriptor("webdav", "storage", "WebDAV", ("upload", "download"))

    def __init__(self, config):
        self.config = config

    def validate(self):
        parsed = urlsplit(self.config.webdav_url)
        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise AdapterError(
                "WEBDAV_CONFIG", "請在環境變數設定 HTTPS WebDAV 目錄與獨立憑證"
            )

    def url(self, name):
        self.validate()
        return self.config.webdav_url.rstrip("/") + "/" + quote(name, safe="")

    def client(self):
        return httpx.AsyncClient(
            auth=(self.config.webdav_user, self.config.webdav_password), timeout=120
        )

    async def upload(self, name, path):
        async with self.client() as client:
            result = await client.put(
                self.url(name),
                content=await asyncio.to_thread(path.read_bytes),
                headers={"Content-Type": "application/zip", "If-None-Match": "*"},
            )
            result.raise_for_status()

    async def download(self, name, path):
        total = 0
        async with self.client() as client:
            async with client.stream("GET", self.url(name)) as response:
                response.raise_for_status()
                with path.open("wb") as out:
                    async for chunk in response.aiter_bytes():
                        total += len(chunk)
                        if total > MAX_DOWNLOAD_BYTES:
                            raise AdapterError("ARCHIVE_LIMIT", "備份下載超過大小上限")
                        out.write(chunk)
