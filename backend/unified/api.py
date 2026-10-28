import secrets
from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter, Depends, HTTPException, Query, WebSocket
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse, StreamingResponse
from .application import Application
from .adapters.contracts import AdapterError
from .config import Config
from .models import (
    HostInput,
    ServiceInput,
    Operation,
    BackupInput,
    RestoreInput,
    ResourceOperation,
    PluginOperation,
    PluginDocument,
    BindingInput,
    SessionInput,
)
from .store import Conflict
from .terminal import serve_terminal

from . import __version__ as VERSION


def create_app(config=None, registry=None):
    config = config or Config.from_env()
    application = Application(config, registry)

    @asynccontextmanager
    async def lifespan(api):
        await application.start()
        yield
        await application.close()

    api = FastAPI(
        title="Unified Application Layer",
        version=VERSION,
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    api.state.application = application
    security = HTTPBearer(auto_error=False)

    async def authenticate(
        credentials: HTTPAuthorizationCredentials | None = Depends(security),
    ):
        if credentials is None or not secrets.compare_digest(
            credentials.credentials, config.token
        ):
            raise HTTPException(
                401, "需要有效的管理員 Token", headers={"WWW-Authenticate": "Bearer"}
            )

    @api.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse(status_code=404, content={"detail": "找不到指定項目"})

    @api.exception_handler(Conflict)
    async def conflict(request, exc):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @api.exception_handler(AdapterError)
    @api.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @api.get("/healthz")
    def health():
        return {"status": "ok", "version": VERSION}

    @api.get("/api/v1/info")
    def info():
        return {
            "version": VERSION,
            "mode": config.mode,
            "terminal": "line-oriented",
            "api_version": 1,
        }

    router = APIRouter(prefix="/api/v1", dependencies=[Depends(authenticate)])

    @router.get("/adapters")
    def adapters():
        return application.registry.catalog()

    @router.get("/snapshot")
    def snapshot():
        return application.snapshot()

    @router.post("/hosts", status_code=201)
    def add_host(body: HostInput):
        return application.add_host(body.model_dump())

    @router.post("/services", status_code=201)
    def add_service(body: ServiceInput):
        if (
            body.adapter in application.registry.services
            and application.registry.service(body.adapter).descriptor.resource_kind
            != "service"
        ):
            raise ValueError("請使用 /resources 登記套件／工具")
        return application.add_service(body.model_dump())

    @router.post("/services/{id}/jobs", status_code=202)
    async def operation(id: str, body: Operation):
        return application.submit(body.action, "service", id, body.scenario)

    @router.get("/plugins")
    def plugins():
        return application.plugins.catalog() if application.plugins else []

    @router.post("/plugin-catalog/refresh")
    def refresh_plugin_catalog():
        return application.refresh_plugin_catalog()

    @router.post("/plugin-documents/validate")
    def validate_document(body: PluginDocument):
        return application.plugin_document("validate", body.manifest)

    @router.post("/plugin-documents", status_code=201)
    def import_document(body: PluginDocument):
        return application.plugin_document("import", body.manifest)

    @router.get("/plugins/{id}/manifest")
    def export_document(id: str):
        manifest = application.plugin_document("export", id=id)
        return JSONResponse(manifest, headers={
            "Content-Disposition": f'attachment; filename="{id}-{manifest["version"]}.json"'
        })

    @router.post("/plugins/{id}")
    def plugin_action(id: str, body: PluginOperation):
        return application.change_plugin(id, body.action, body.version, body.checksum)

    @router.get("/resources")
    def resources():
        return application.snapshot()["resources"]

    @router.post("/resources/{id}")
    def edit_resource(id: str, body: ServiceInput):
        return application.edit_resource(id, body.model_dump())

    @router.post("/resources", status_code=201)
    def add_resource(body: ServiceInput):
        with application.guard:
            return application.add_service(body.model_dump())

    @router.post("/resources/{id}/bindings", status_code=201)
    def binding(id: str, body: BindingInput):
        return application.bind_resource(id, body.model_dump())

    @router.post("/resources/{id}/jobs", status_code=202)
    async def resource_job(id: str, body: ResourceOperation):
        return await application.submit_resource(id, body)

    @router.get("/jobs/{id}/session")
    def session(id: str):
        application.store.job(id)
        return application.sessions.view(id)

    @router.post("/jobs/{id}/session")
    async def session_input(id: str, body: SessionInput):
        application.store.job(id)
        return await application.sessions.input(
            id, body.generation, body.sequence, body.data, body.close
        )

    @router.post("/backups", status_code=202)
    async def backup(body: BackupInput):
        return application.submit("backup", "client", body.client, body.scenario)

    @router.post("/backups/{id}/restore", status_code=202)
    async def restore(id: str, body: RestoreInput):
        return application.submit("restore", "backup", id, body.scenario)

    @router.get("/jobs/{id}")
    def job(id: str):
        return application.store.job(id)

    @router.get("/jobs/{id}/logs")
    def logs(id: str, after: int = Query(default=0, ge=0)):
        application.store.job(id)
        return application.store.logs(id, after)

    @router.get("/jobs/{id}/log.txt")
    def download(id: str):
        application.store.job(id)

        def chunks():
            cursor = 0
            while rows := application.store.logs(id, cursor):
                for row in rows:
                    yield f"[{row['time']}] [{row['stream']}] {row['text']}"
                cursor = rows[-1]["seq"]

        return StreamingResponse(
            chunks(),
            media_type="text/plain",
            headers={"Content-Disposition": f'attachment; filename="{id}.log"'},
        )

    api.include_router(router)

    @api.websocket("/api/v1/hosts/{id}/terminal")
    async def terminal(socket: WebSocket, id: str):
        await serve_terminal(socket, application, id)

    return api
