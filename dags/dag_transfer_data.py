from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.postgres.operators.postgres import PostgresOperator
import requests
import pandas as pd
import logging
from datetime import datetime, timedelta
import os


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
    start_date=datetime(2025, 3, 1),
    description="Transfer data to Postgres-2 database"
) as dag:

    dag.doc_md = """This DAG performs transferring data from Postgres-1 to Postgres-2 database"""

    def get_currencies_rates():
        response = requests.get(url=f"{URL_RATES}?app_id={API_KEY}", headers={'Accept': 'application/json'})

        if response.status_code == 200:
            logging.info("Currencies rates successfully retrieved")
            return response.json()["rates"]
        else:
            logging.error("Something went wrong while retrieving currencies rates")
            raise Exception

    def process_data(**kwargs):
        hook_postgres_1 = PostgresHook(postgres_conn_id='postgres_conn_1')
        hook_postgres_2 = PostgresHook(postgres_conn_id='postgres_conn_2')

        currency_rates: dict = kwargs['ti'].xcom_pull(task_ids='get_currencies_rates')

        records = hook_postgres_1.get_records("SELECT * FROM orders")

        data = []
        for record in records:
            if record[4] in currency_rates:
                amount_rate = float(record[3]) / currency_rates[record[4]]
                data.append(
                    {'order_id': record[0], 'customer_email': record[1], 'order_date': record[2], 'amount': amount_rate,
                     'currency_usd': "USD"})
        df = pd.DataFrame(data)

        df.to_sql('orders_usd', con=hook_postgres_2.get_sqlalchemy_engine(), if_exists='replace', index=False)
        logging.info(f"Converted data successfully inserted to orders_usd table!")


    create_orders_eur_table_task = PostgresOperator(
        task_id='create_orders_usd_table',
        postgres_conn_id='postgres_conn_2',
        sql="""CREATE TABLE IF NOT EXISTS orders_usd (
                    order_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    customer_email VARCHAR(255) NOT NULL,
                    order_date TIMESTAMP NOT NULL DEFAULT NOW(),
                    amount NUMERIC(10,2) NOT NULL,
                    currency_usd VARCHAR(10) NOT NULL
                );""",
        dag=dag
    )

    get_currencies_rates_task = PythonOperator(
        task_id='get_currencies_rates',
        python_callable=get_currencies_rates,
        dag=dag,
        do_xcom_push=True
    )

    process_data_from_postgres_1_task = PythonOperator(
        task_id='fetch_data_from_postgres_1',
        python_callable=process_data,
        dag=dag
    )


    create_orders_eur_table_task >> get_currencies_rates_task >> process_data_from_postgres_1_task




