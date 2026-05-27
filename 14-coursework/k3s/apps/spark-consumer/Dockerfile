FROM bitnami/spark:3.5.0

USER root

COPY kafka_to_minio.py /opt/spark/work-dir/
COPY requirements.txt  /opt/spark/work-dir/

RUN pip install --no-cache-dir -r /opt/spark/work-dir/requirements.txt

USER 1001

WORKDIR /opt/spark/work-dir
