FROM refraction-api:local
USER root
COPY apps/api/requirements-dev.txt ./requirements-dev.txt
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY apps/api/pyproject.toml ./pyproject.toml
COPY apps/api/tests ./tests
COPY tests/fixtures /tests/fixtures
USER 10001:10001
CMD ["python", "-m", "pytest", "-c", "pyproject.toml", "tests", "-q", "-o", "cache_dir=/tmp/pytest-cache", "--basetemp", "/tmp/pytest"]
