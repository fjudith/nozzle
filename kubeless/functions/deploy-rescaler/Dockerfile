ARG PYTHON_VERSION="3.8"
FROM docker.io/kubeless/python:${PYTHON_VERSION}

LABEL maintainer="Florian JUDITH <florian.judith.b@gmail.com>"

ENV FUNC_HANDLER="handle" \
    MOD_NAME="handler" \
    KUBELESS_INSTALL_VOLUME="/kubeless"

ENV KUBELESS_DEPS_FILE="${KUBELESS_INSTALL_VOLUME}/requirements.txt" \
    PYTHONPATH="${PYTHONPATH}:${KUBELESS_INSTALL_VOLUME}/lib/python${PYTHON_VERSION}/site-packages:${KUBELESS_INSTALL_VOLUME}" \
    PATH="${PATH}:${KUBELESS_INSTALL_VOLUME}/bin"

USER root

RUN mkdir -p /kubeless /function

# Install required dependencies
COPY ./requirements.txt /kubeless/
# RUN pip install --prefix=${KUBELESS_INSTALL_VOLUME} -r ${KUBELESS_DEPS_FILE}
RUN pip install -r ${KUBELESS_DEPS_FILE}
# Rescaler Website pod specification and static content
COPY ./templates /function/templates

# Rescaler function
COPY ./handler.py /kubeless/

# Enforce permissions
RUN chown -R 1000:1000 /kubeless /function && \
    chmod 644 /kubeless/handler.py /kubeless/requirements.txt

USER 1000