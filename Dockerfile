FROM apache/airflow:2.10.5
USER airflow

# Встановлюємо потрібний пакет
RUN pip install --no-cache-dir apache-airflow-providers-postgres==5.14.0
