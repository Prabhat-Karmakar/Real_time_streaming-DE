import logging
from datetime import datetime

from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import Cluster
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col
from pyspark.sql.types import StructType, StructField, StringType


#Creating a Keyspace ---
def create_keyspace(session):
    session.execute("""
            CREATE KEYSPACE IF NOT EXISTS spark_streams
            WITH replication = {'class': 'SimpleStrategy', 'replication_factor': '1'};
        """)

    print("Keyspace created successfully!")


#Create a Table ---
def create_table(session):
    session.execute("""
    CREATE TABLE IF NOT EXIST streamed_users_created(
        id UUID PRIMARY KEY,
        first_name TEXT,
        last_name TEXT,
        gender TEXT,
        address TEXT,
        postcode TEXT,
        email TEXT,
        username TEXT,
        dob TEXT,
        registered_date TEXT,
        phone TEXT
    """)

    print("Table Created Successfully!")


#Data Insertion   ---
def insert_data(session, **kwargs):
    print("Inserting Data ...")

    user_id = kwargs.get('id')
    first_name = kwargs.get('first_name')
    last_name = kwargs.get('last_name')
    gender = kwargs.get('gender')
    address = kwargs.get('address')
    postcode = kwargs.get('postcode')
    email = kwargs.get('email')
    username = kwargs.get('username')
    dob = kwargs.get('dob')
    registered_date = kwargs.get('registered_date')
    phone = kwargs.get('phone')


    try:
        session.execute("""
            INSERT INTO spark_streams.created_users(id, first_name, last_name, gender, address, 
                       post_code, email, username, dob, registered_date, phone)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               """,
                        (user_id, first_name, last_name, gender, address,
                     postcode, email, username, dob, registered_date, phone))
        logging.info(f"Data inserted for {first_name} {last_name}")

    except Exception as e:
        logging.error(f' Could not insert data due to {e}')



#Creating Spark Connection  ---
def create_spark_connection():
    s_conn = None

    try:
        s_conn = SparkSession.builder \
            .appName('SparkStreaming') \
            .config('spark.jars.packages', "com.datastax.spark:spark-cassandra-connector_2.13:3.5.0,"
                                           "org.apache.spark:spark-sql-kafka-0-10_2.13:3.5.1") \
            .config('spark.cassandra.connection.host', 'localhost') \
            .getOrCreate()
        s_conn.sparkContext.setLogLevel("Error")
        logging.info("Spark Connection created successfully")

    except Exception as e:
        logging.error(f"Could'nt Create the Spark Connection due to exception {e}")

    return s_conn

#Create a connection to Kafka to retrieve Streamed Data
def connect_to_kafka(spark_conn):
    spark_df = None
    try:
        spark_df = spark_conn.readStream \
             .format('kafka') \
             .option('kafka_bootstrap.servers', 'localhost:9092') \
             .option('subscribe', 'users_created') \
             .option('startingOffsets', 'earliest') \
             .load()
        logging.info("Initial Dataframe Created Successfully")
    except Exception as e:
        logging.warning(f"Kafka Dataframe coldn't be created because : {e}")

    return spark_df



# Creating Cassandra Connection ---
def create_cassandra_connection():
    try:

        cluster = Cluster(['localhost'])

        cas_session = cluster.connect()

        return cas_session

    except Exception as e:
        logging.error(f"Couldn't Create cassandra Connection due to {e}")
        return None


def create_Selected_df_from_kafka(spark_df):
    schema = StructType([
        StructField("id", StringType(), False),
        StructField("first_name", StringType(), False),
        StructField("last_name", StringType(), False),
        StructField("gender", StringType(), False),
        StructField("address", StringType(), False),
        StructField("postcode", StringType(), False),
        StructField("email", StringType(), False),
        StructField("username", StringType(), False),
        StructField("dob", StringType(), False),
        StructField("registered_date", StringType(), False),
        StructField("phone", StringType(), False),

    ])

    sel = spark_df.selectExpr("CAST(value AS STRING)")\
          .select(from_json(col('value'), schema).alias('data')).select('data.*')
    print(sel)

    return sel


if __name__ == "__main__":
    spark_conn = create_spark_connection()

    if spark_conn is not None:
        spark_df = connect_to_kafka(spark_conn)
        selected_df = create_Selected_df_from_kafka(spark_df)
        session = create_cassandra_connection()

        if session is not None:
            create_keyspace(session)
            create_table(session)
            # insert_data(session)

            streaming_query = (selected_df.writeStream.format('org.apache.spark.sql.cassandra')
                               .option('checkpointLocation','/tmp/checkpoint')
                               .option('keyspace','spark_streams')
                               .option('table', 'created_user')
                               .start())

            streaming_query.awaitTermination()
