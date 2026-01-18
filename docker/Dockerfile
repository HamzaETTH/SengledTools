# Build the container from the repo root using:
# `docker build -t sengledtools -f docker/Dockerfile .`

FROM python:3.14-alpine

COPY --parents sengled/ sengled_tool.py requirements.txt /app
RUN pip install -r /app/requirements.txt && \
    rm -rf /root/.cache/pip

WORKDIR /app
CMD python -u sengled_tool.py \
    --run-http-server \
    $(test -n "$BROKER_IP" && echo "--broker-ip $BROKER_IP") \
    $(test -n "$BROKER_PORT" && echo "--broker-port $BROKER_PORT") \
    ${SENGLED_TOOL_ARGS}

EXPOSE 57542
