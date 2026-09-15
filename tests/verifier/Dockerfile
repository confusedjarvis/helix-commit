FROM python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/tests/verifier \
    HELIX_REPO=/app \
    TZ=UTC \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

RUN groupadd --gid 10001 candidate \
    && useradd --uid 10001 --gid 10001 --home-dir /home/candidate --create-home --shell /usr/sbin/nologin candidate \
    && mkdir -p /tests/verifier /app \
    && chmod 0700 /tests/verifier

COPY . /tests/verifier

RUN chown -R root:root /tests/verifier \
    && find /tests/verifier -type d -exec chmod 0700 {} \; \
    && find /tests/verifier -type f -exec chmod 0600 {} \; \
    && chmod 0700 /tests/verifier/run.sh

WORKDIR /tests/verifier
USER root

CMD ["python3", "-m", "unittest", "-v", "test_outputs"]
