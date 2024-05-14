import uuid
import logging
from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
import requests
import json
from kafka import KafkaProducer
import time


default_args = {
    'owner': 'Prabhat',
    'start_date': datetime(2024, 1, 5,10,00,00)}


def get_data():
    res = requests.get("https://randomuser.me/api/?nat=IN,US")
    res = res.json()
    res =res['results'][0]
    return res

def clean_data(res):
    data = {}
    data['first_name']=res['name']['first']
    data['last_name'] = res['name']['last']
    data['gender'] = res['gender']
    data['address'] = (f"{res['location']['street']['number']},{res['location']['street']['name']}," 
                       f"{res['location']['city']}, {res['location']['state']}, {res['location']['country']}")
    data['postcode'] = res['location']['postcode']
    data['email'] = res['email']
    data['username'] = res['login']['username']
    data['dob'] = res['dob']['date'].split('T')[0]
    data['registered_date'] = res['registered']['date'].split('T')[0]
    data['phone'] = res['phone']

    return data

def stream_data():

    res = get_data()
    res = clean_data(res)
    producer = KafkaProducer(bootstrap_servers=['kafka:29092'] , max_block_ms=6000)
    curr_time = time.time()

    while True:
        if time.time() > curr_time + 60:
            break
        try:
            res = get_data()
            res = clean_data(res)

            producer.send('users_created', json.dumps(res).encode('utf-8'))

        except Exception as e:
            logging.error(f'An error occured: {e}')
            continue

with DAG('user_automation',
         default_args=default_args,
         schedule_interval='@daily',
         catchup=False) as dag:
    streaming_task = PythonOperator(
        task_id='stream_from_api',
        python_callable=stream_data
    )


# stream_data()