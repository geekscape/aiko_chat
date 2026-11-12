# AIKO_SERVICES_SPEC is any pip requirement specifier.  Default: GitHub `master`.
#   --build-arg AIKO_SERVICES_SPEC='aiko_services'          # latest from PyPI
#   --build-arg AIKO_SERVICES_SPEC='aiko_services==X.Y.Z'   # pinned PyPI version
#   --build-arg AIKO_SERVICES_SPEC='aiko_services @ git+https://github.com/<fork>/aiko_services.git@<branch>'
FROM python:3.13 AS build
ARG AIKO_SERVICES_SPEC='aiko_services @ git+https://github.com/geekscape/aiko_services.git@master'
RUN pip wheel --no-deps -w /wheels "${AIKO_SERVICES_SPEC}"

# NOTE(nic): apply the patches needed to get this running in a container,
#  talking to Docker Model Runner.  As the patches get folded in, remove them
#  from `docker/patches/`.  This step should be future-proof and continue to
#  work, even if the `docker/patches/` directory is empty/non-existent.
WORKDIR /build/aiko_chat
COPY . .
RUN set -eux ; \
    set -- docker/patches/*.patch ; \
    [ ! -e "$1" ] || git apply "$@"

# NOTE(nic): The current deployment target is a container that runs the
#  aiko_chat server.  That service only requires a subset of the functionality
#  required by Aiko Services, and therefore only requires a subset of
#  third-party dependencies.  So this Dockerfile ends up being a mixture of
#  container best practices and project-specific workarounds, to keep the image
#  size down:
#
#   - Prevent bytecode files from being generated on package install.  The
#     container regenerates these anyhow, so they just waste space
#
#   - Prefer `uv` over `pip` as the package manager, as it is (much) faster and
#     has a (much) better solver
#
#   - But once the build is done, `uv` provides no more value and takes up a ton
#     of room, so remove it at the end of the install
#
#   - Install only the subset of packages required to get the registrar running.
#     This is brittle and likely the first thing to break on code changes, but
#     it does prevent things like NumPy and requests from getting installed into
#     a container that will literally never use them
FROM python:3.13-slim

COPY --from=build /build/aiko_chat /app
COPY --from=build /wheels /wheels

WORKDIR /app
ARG PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN set -eux ; \
    pip install --no-compile --no-cache-dir uv ; \
    uv pip install --system langchain_openai langchain_ollama psutil paho-mqtt \
            transitions wrapt click avro avro-validator asciimatics pyperclip ; \
    uv pip install --system --no-index --no-deps --find-links /wheels aiko_services ; \
    uv pip install --system --no-deps -e /app ; \
    uv pip uninstall --system uv ; \
    rm -rf /root/.cache

ENTRYPOINT ["src/aiko_chat/chat_start.sh"]
CMD ["llm"]

LABEL org.opencontainers.image.source=https://github.com/0xdec0de/aiko_chat
LABEL org.opencontainers.image.description="Chat system built on top of Aiko Services"
LABEL org.opencontainers.image.licenses="Apache-2.0"
