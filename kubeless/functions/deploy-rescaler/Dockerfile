FROM kubeless/python:3.6

LABEL maintainer="Florian JUDITH <florian.judith.b@gmail.com>"

ENV FUNC_HANDLER="handle" \
    MOD_NAME="handler" \
    KUBELESS_INSTALL_VOLUME="/kubeless"

ENV KUBELESS_DEPS_FILE="${KUBELESS_INSTALL_VOLUME}/requirements.txt" \
    PYTHONPATH="${KUBELESS_INSTALL_VOLUME}/lib/python3.6/site-packages:${KUBELESS_INSTALL_VOLUME}" \
    PATH="${PATH}:${KUBELESS_INSTALL_VOLUME}/bin"

USER root

RUN mkdir -p /kubeless /function

# Rescaler function
COPY ./handler.py /
COPY ./requirements.txt /kubeless/

# Rescaler Website pod specification and static content
COPY ./templates        /function/templates

# Install required dependencies
RUN pip install --prefix=${KUBELESS_INSTALL_VOLUME} -r ${KUBELESS_DEPS_FILE} && \
    chown -R 1000:1000 /handler.py /kubeless /function && \
    chmod 644 /handler.py /kubeless/requirements.txt

USER 1000

ENTRYPOINT [ "/bin/bash", "-c", "cp /handler.py /kubeless/ && python /kubeless.py" ]