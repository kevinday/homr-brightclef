# Standalone engine build; context is this component directory only.
# The build target needs no models, worker code, private input or credentials.
# The runtime target installs RapidOCR with its bundled OCR models; it does not
# initialize HOMR checkpoints. Build only --target build when models are forbidden.
FROM python:3.11-slim-bookworm@sha256:2e32f7d302adc1c37428355c1e646897c0c53f4fd60b6a551245fb90ee129f91 AS build
RUN apt-get update && apt-get install --yes --no-install-recommends patch \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
COPY . /component
RUN python /component/build/build.py --out /dist

FROM python:3.11-slim-bookworm@sha256:2e32f7d302adc1c37428355c1e646897c0c53f4fd60b6a551245fb90ee129f91
RUN apt-get update && apt-get install --yes --no-install-recommends libgl1 libglib2.0-0 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
COPY --from=build /component /component
COPY --from=build /dist /dist
RUN bash /component/build/install.sh --python python --venv /opt/homr --closure runtime \
    --wheel /dist/homr-0.7.0+brightclef.export3-py3-none-any.whl \
    --wheel-sha256 f4a61e1bf12709a011dd8d9e497b4bd7eba2d0fb613655c7d8d7267b39c6d93e
ENV PYTHONDONTWRITEBYTECODE=1
WORKDIR /data
ENTRYPOINT ["/opt/homr/bin/homr"]
CMD ["--help"]
