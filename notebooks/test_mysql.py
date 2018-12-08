import pandas as pd
from sqlalchemy import create_engine

conn_string = 'mysql://{user}:{password}@{host}/?charset=utf8'.format(
    host = 'db.ipeirotis.org', 
    user = 'student',
    password = 'dwdstudent2015',
    encoding = 'utf-8')
engine = create_engine(conn_string)

df = pd.read_sql("SELECT * FROM imdb.movies WHERE id<100", con=engine)
assert len(df)==96