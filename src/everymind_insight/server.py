"""Loopback-only FastAPI dashboard. Survey uploads and caches stay in memory."""
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .filter_service import FilterService, export_report
from .filters import FilterSpec

ROOT = Path(__file__).resolve().parents[2]
MAX_UPLOAD = 50 * 1024 * 1024


def create_app(input_path=None, *, root=ROOT):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1'])
    app.state.service = FilterService(Path(input_path)) if input_path else None

    @app.middleware('http')
    async def local_boundary(request, call_next):
        origin = request.headers.get('origin')
        if origin and origin != f"{request.url.scheme}://{request.headers.get('host')}":
            return JSONResponse({'detail':'Only this local page may access the survey.'},status_code=403)
        if request.headers.get('sec-fetch-site') == 'cross-site':
            return JSONResponse({'detail':'Cross-site access is disabled.'},status_code=403)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_spec(request, error):
        return JSONResponse({'detail':[{'loc':e['loc'],'msg':e['msg']} for e in error.errors()]},status_code=422)

    def service(request):
        current = app.state.service
        if current is None: raise HTTPException(409, 'Select an XLSX or CSV survey first. Aggregate reports have no source rows to filter.')
        expected = request.headers.get('x-input-hash')
        if expected and expected != current.input_hash: raise HTTPException(409,'The selected survey changed. Reopen data options.')
        return current

    async def limited_body(request, limit):
        chunks, size = [],0
        async for chunk in request.stream():
            size += len(chunk)
            if size > limit: raise HTTPException(413, 'This file exceeds the local upload limit.')
            chunks.append(chunk)
        return b''.join(chunks)

    async def spec_from(request):
        from pydantic import ValidationError
        try: return FilterSpec.model_validate_json(await limited_body(request,64*1024))
        except ValidationError as error:
            raise RequestValidationError(error.errors()) from None

    @app.get('/api/fields')
    def fields():
        if app.state.service is None:
            return {'available':False,'message':'Choose an XLSX or CSV survey to enable data options. JSON reports contain aggregates only.'}
        return app.state.service.fields()

    @app.post('/api/source')
    async def source(request: Request, filename: str, sheet: str | None = None):
        suffix = Path(filename).suffix.lower()
        if suffix not in {'.xlsx','.csv'}: raise HTTPException(422,'Choose an XLSX or UTF-8 CSV survey export.')
        data = await limited_body(request,MAX_UPLOAD)
        try: candidate = await run_in_threadpool(FilterService,data,suffix=suffix,sheet=sheet)
        except (ValueError, OSError): raise HTTPException(422,'The survey could not be read. Check its format, worksheet, ID and paired-question headers; at least 10 usable responses are required.') from None
        app.state.service = candidate
        return candidate.fields()

    @app.post('/api/preview')
    async def preview(request: Request):
        current, spec = service(request), await spec_from(request)
        try: return await run_in_threadpool(current.preview,spec)
        except ValueError as error: raise HTTPException(422,str(error)) from None

    @app.post('/api/report')
    async def report(request: Request):
        current, spec = service(request), await spec_from(request)
        try: return (await run_in_threadpool(current.open_report,spec)).model_dump(mode='json')
        except ValueError as error: raise HTTPException(422,str(error)) from None

    @app.post('/api/export/{format}')
    async def export(format: str, request: Request):
        if format not in {'json','csv','parquet'}: raise HTTPException(404,'Choose json, csv, or parquet.')
        current, spec = service(request), await spec_from(request)
        try:
            bundle = await run_in_threadpool(current.open_report,spec)
            data = await run_in_threadpool(export_report,bundle,format)
        except ValueError as error: raise HTTPException(422,str(error)) from None
        media = {'json':'application/json','csv':'text/csv','parquet':'application/vnd.apache.parquet'}[format]
        return Response(data,media_type=media,headers={'Content-Disposition':f'attachment; filename="everymind-report.{format}"'})

    @app.get('/report.json')
    def initial_report():
        # Opening data options is explicit; no analysis runs just to load the page.
        raise HTTPException(404,'Choose Open report to choose data options.')

    @app.get('/report.synthetic.json')
    def synthetic(): return FileResponse(root / 'fixtures/report.sample.json',media_type='application/json')

    @app.get('/assets/{asset_path:path}')
    def asset(asset_path: str):
        base = (root / 'dashboard/assets').resolve()
        target = (base / asset_path).resolve()
        if not target.is_relative_to(base) or not target.is_file() or target.suffix.lower() not in {'.mp4','.jpg','.png','.ttf','.woff','.woff2','.txt','.md'}:
            raise HTTPException(404)
        return FileResponse(target)

    @app.get('/')
    def index(): return FileResponse(root / 'dashboard/index.html')

    @app.get('/{name}')
    def runtime(name: str):
        if name not in {'index.html','app.js','styles.css','report-data.js','data-options.js'}: raise HTTPException(404)
        return FileResponse(root / 'dashboard' / name)
    return app
