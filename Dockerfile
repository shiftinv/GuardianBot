FROM python:3.9-alpine

# add user
RUN adduser -DH app \
 && mkdir /app \
 && chown -R app:app /app
WORKDIR /app

# install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy app
USER app
COPY --chown=app:app . .
RUN mkdir data

VOLUME /app/data
CMD ["python", "-m", "guardianbot"]
