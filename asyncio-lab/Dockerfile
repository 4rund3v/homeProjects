# docs/05: the container is a probe, not a dependency.
# The tool is stdlib-only; uv sync --frozen makes the image reproducible
# (the same "pinned, no float" idea as traffic-analysis/project/labs/registry.md).
FROM python:3.11-slim
WORKDIR /app

COPY pyproject.toml .
RUN pip install uv && uv sync --frozen

COPY app/ app/
COPY internal/ internal/

# CLI by default; --serve for the k8s Service (docs/05)
ENTRYPOINT ["uv", "run", "dupfind"]
CMD ["--help"]
