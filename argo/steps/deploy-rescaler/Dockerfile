FROM docker.io/amd64/python:3.6-alpine

LABEL maintainer="Florian JUDITH <florian.judith.b@gmail.com>"

ARG USER="nozzle"
ARG GROUP="restricted"
ARG UID="1010"
ARG GID="1010"

ENV USER_HOME="/home/${USER}"

ENV DEPS_FILE="${USER_HOME}/requirements.txt" \
    PYTHONPATH="${USER_HOME}/lib/python3.6/site-packages:${USER_HOME}" \
    PATH="${PATH}:${USER_HOME}/bin"

# Enable root during build, admin operations and dependencies processing
USER root

# Create a group and user
RUN  addgroup -g ${GID} ${GROUP} && \
     adduser -u ${UID} -D -g '' -h ${USER_HOME} -G ${GROUP} ${USER} && \
     mkdir -p ${USER_HOME}/function

# Install required dependencies
COPY ./requirements.txt ${USER_HOME}/
RUN apk add --update --no-cache ca-certificates gcc build-base & \
    pip install --no-cache-dir --prefix=${USER_HOME} -r ${DEPS_FILE}

# Rescaler function
COPY ./handler.py ${USER_HOME}/function/
COPY ./templates ${USER_HOME}/function/templates

# Enforce permissions
RUN chown -R ${UID}:${UID} ${USER_HOME}/function

# Enable the secure custom user 
USER ${USER}

WORKDIR ${USER_HOME}/function

CMD ["python", "handler.py"]
