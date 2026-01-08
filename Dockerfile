
ARG UID=0
ARG GID=0

FROM containers.cisco.com/cway/node-alpine-hardened:22.21.1 AS build
LABEL quay.expires_after=""

WORKDIR /app

COPY ["package*.json", "./"]

RUN npm ci

COPY . .
RUN npm run build


FROM containers.cisco.com/jorcleme/netacad-gradebook-manager-db:latest AS database
LABEL quay.expires_after=""

FROM python:3.12-slim-bookworm AS base

ARG UID
ARG GID

## Basis ##
ENV ENV=prod \
    NODE_ENV="production" \
    PORT=8000

ENV SECRET_KEY=""

WORKDIR /app/backend

RUN mkdir -p /app/backend/data


ENV HOME=/root

# install python dependencies
COPY ./backend/requirements.txt ./requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers and dependencies as root
# This must happen before switching to non-root user
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN playwright install --with-deps chromium && \
    chmod -R 755 /ms-playwright

# Create user and group if not root
RUN if [ $UID -ne 0 ]; then \
    if [ $GID -ne 0 ]; then \
    addgroup --gid $GID app; \
    fi; \
    adduser --uid $UID --gid $GID --home $HOME --disabled-password --no-create-home app; \
    fi

# Make sure the user has access to the app and root directory
RUN chown -R $UID:$GID /app $HOME

# copy built frontend files
COPY --chown=$UID:$GID --from=build /app/build /app/build
COPY --chown=$UID:$GID --from=build /app/package.json /app/package.json

# copy backend files
COPY --chown=$UID:$GID ./backend .

# copy database file from database image
COPY --chown=$UID:$GID --from=database ./netacad.db /app/backend/data/netacad.db

# Fix ownership and perms recursively, including subdirs
RUN chgrp -R $GID /app/backend && \
    chmod -R g=u /app/backend

EXPOSE 8000

HEALTHCHECK CMD curl --silent --fail http://localhost:${PORT:-8000}/health | jq -ne 'input.status == true' || exit 1

USER $UID:$GID

CMD [ "bash", "start.sh" ]