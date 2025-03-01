from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.postgres.operators.postgres import PostgresOperator
import requests
import pandas as pd
import logging
from datetime import datetime, timedelta
import os
from airflow.decorators import task

API_KEY = os.getenv("API_KEY")
URL_RATES = "https://openexchangerates.org/api/latest.json"



default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email': ['kucikm23@gmail.com'],
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'tags': ['airflow'],
}

with DAG (
    dag_id='dag_transfer_data',
    default_args=default_args,
    schedule_interval='@hourly',
    catchup=False,
    start_date=datetime.now(),
    description="Transfer data to Postgres-2 database"
) as dag:
    dag.doc_md = """This DAG performs transferring data from Postgres-1 to Postgres-2 database"""

    def get_currencies_rates():
        response = requests.get(url=f"{URL_RATES}?app_id={API_KEY}", headers={'Accept': 'application/json'})

        if response.status_code == 200:
            print(response.json())
        else:
            print(response.status_code, response.json())

    def fetch_data():
        hook = PostgresHook(postgres_conn_id='postgres_conn_1')

        records = hook.get_records("SELECT * FROM orders")



    create_orders_eur_table_task = PostgresOperator(
        task_id='create_orders_eur_table',
        postgres_conn_id='postgres_conn_2',
        sql="""CREATE TABLE IF NOT EXISTS orders_eur (
                    order_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    customer_email VARCHAR(255) NOT NULL,
                    order_date TIMESTAMP NOT NULL DEFAULT NOW(),
                    amount NUMERIC(10,2) NOT NULL,
                    currency_eur VARCHAR(10) NOT NULL
                );""",
        dag=dag
    )

    fetch_data_from_postgres_1_task = PythonOperator(
        task_id='fetch_data_from_postgres_1',
        python_callable=fetch_data,
        dag=dag
    )

    get_currencies_rates_task = PythonOperator(
        task_id='get_currencies_rates',
        python_callable=get_currencies_rates,
        dag=dag
    )

    create_orders_eur_table_task >> get_currencies_rates_task >> fetch_data_from_postgres_1_task




