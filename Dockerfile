FROM python:3.9-alpine

# add user
RUN adduser -DH app \
 && mkdir /app \
 && chown -R app:app /app
WORKDIR /app

# install dependencies
COPY requirements.txt .
RUN apk add --no-cache --virtual build-dep git build-base \
 && pip install --no-cache-dir -r requirements.txt \
 && apk del build-dep \
 && find /tmp/ /var/tmp/ -mindepth 1 -maxdepth 1 -exec rm -rf "{}" +

# copy app
USER app
COPY --chown=app:app . .
RUN mkdir data

VOLUME /app/data
CMD ["python", "-m", "guardianbot"]
