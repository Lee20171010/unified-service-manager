FROM python:3.12-alpine@sha256:5789aa194f757888f41fa3d48e14b6feaa1b57c0af0b56fcb1372d6474d3bff0
WORKDIR /app
COPY backend/requirements.txt backend/requirements-lock.txt ./
RUN apk add --no-cache setpriv=2.42.3-r1 \
    && pip install --only-binary=:all: --no-cache-dir -r requirements.txt \
    && python -m pip uninstall -y pip setuptools \
    && addgroup -g 10001 unified \
    && adduser -D -u 10001 -G unified unified
RUN command -v setpriv
COPY backend/unified ./unified
COPY --chmod=755 backend/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
COPY plugins/service-management/compose /builtin-plugins/service-management/compose
COPY plugins/package-management/npm-packages /builtin-plugins/package-management/npm-packages
COPY plugins/backup-storage/webdav /builtin-plugins/backup-storage/webdav
ENV BUILTIN_PLUGINS=/builtin-plugins
RUN mkdir /data && chown unified:unified /data
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
EXPOSE 8000
CMD ["uvicorn", "unified.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--ws-max-size", "16384"]
