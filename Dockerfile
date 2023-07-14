# Container image that runs the action
FROM python:alpine

COPY . .
RUN pip install -r requirements.txt

COPY main.py /
COPY entrypoint.sh /


WORKDIR /github/workspace
ENTRYPOINT ["sh", "/entrypoint.sh"]
