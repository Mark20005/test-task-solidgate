from datetime import datetime, timedelta
import uuid
import random
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.postgres.operators.postgres import PostgresOperator
import requests
import pandas as pd
import logging

EXCHANGE_URL = "https://openexchangerates.org/api/currencies.json"
current_date = datetime.now()

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

with DAG(
        dag_id='dag_generate_table_info',
        default_args=default_args,
        description='Create and populate orders table in Postgres-1',
        schedule_interval="*/10 * * * *",
        catchup=False,
        start_date=datetime.now(),
) as dag:

    dag.doc_md = """ This DAG performs creating and generating data for orders table in Postgres-1 DB"""

    def get_currency_list():
        response = requests.get(url=EXCHANGE_URL)

        if response.status_code == 200:
            logging.info("Currency list successfully fetched!")
            return list(response.json().keys())
        else:
            logging.error("Failed to fetch currency list!")
            return None


    def generate_table_info(**kwargs) -> pd.DataFrame:
        currencies = kwargs['ti'].xcom_pull(task_ids='get_api_currency')
        two_weeks_ago = current_date - timedelta(weeks=3)

        data = []
        for _ in range(20000):
            order_id = str(uuid.uuid4())
            customer_email = f'user{random.randint(1, 10000)}@example.com'
            order_date = two_weeks_ago + timedelta(days=random.randint(0, (current_date - two_weeks_ago).days))
            amount = round(random.uniform(10.0, 1000.0), 2)
            currency = random.choice(currencies)

            # Додаємо дані в список
            data.append({'order_id': order_id, 'customer_email': customer_email,
                         'order_date': order_date, 'amount': amount, 'currency': currency})

        df = pd.DataFrame(data)

        logging.info("Sample data successfully generated!")
        return df


    def insert_orders_data(**kwargs):
        hook = PostgresHook(postgres_conn_id='postgres_conn_1')
        df: pd.DataFrame = kwargs['ti'].xcom_pull(task_ids='generate_orders_data')

        df = df[(df['order_date'] >= current_date - timedelta(days=7)) & (df['order_date'] <= current_date)]
        df = df.sample(n=5000)

        df.to_sql('orders', con=hook.get_sqlalchemy_engine(), if_exists='append', index=False)
        logging.info(f"Filtered data successfully inserted to orders table in amount of {len(df)} rows!")


    create_order_table_task = PostgresOperator(
        task_id='create_order_table_orders',
        postgres_conn_id='postgres_conn_1',
        sql="""CREATE TABLE IF NOT EXISTS orders (
                order_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                customer_email VARCHAR(255) NOT NULL,
                order_date TIMESTAMP NOT NULL DEFAULT NOW(),
                amount NUMERIC(10,2) NOT NULL,
                currency VARCHAR(10) NOT NULL
            );""",
        dag=dag
    )

    get_currency_task = PythonOperator(
        task_id='get_api_currency',
        python_callable=get_currency_list,
        dag=dag,
        do_xcom_push=True
    )

    generate_table_info_task = PythonOperator(
        task_id='generate_orders_data',
        python_callable=generate_table_info,
        dag=dag,
        provide_context=True,
        do_xcom_push=True
    )

    insert_orders_task = PythonOperator(
        task_id='insert_orders',
        python_callable=insert_orders_data,
        dag=dag,
        provide_context=True
    )

    create_order_table_task >> get_currency_task >> generate_table_info_task >> insert_orders_task