FROM python:3.12

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./src /code/src

COPY ./data /code/data

CMD ["fastapi", "run", "src/ad_creative_generator/main.py", "--port", "80"]