import pandas as pd
import locale
import logging

def init():
    # configure logging
    logger = logging.getLogger()
    handler = logging.FileHandler('.log','w')
    formatter = logging.Formatter('[%(asctime)s] %(levelname)-8s %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    
    # configure locale
    locale.setlocale(locale.LC_TIME, "en_US.utf8")

def readCSV():
    logging.info('Reading CSV...')
    return pd.read_csv('accidents.csv', dtype = 'object')

def checkColumns(data):
    errors = False
    logging.info('***Checking if any columns have benn removed or added to the dataset.***')
    # Check if all columns needed are in the dataset
    VALUES = [
        'DATE','TIME','BOROUGH','ZIP CODE','LATITUDE','LONGITUDE','LOCATION',
        'ON STREET NAME','CROSS STREET NAME','OFF STREET NAME','NUMBER OF PERSONS INJURED',
        'NUMBER OF PERSONS KILLED','NUMBER OF PEDESTRIANS INJURED','NUMBER OF PEDESTRIANS KILLED',
        'NUMBER OF CYCLIST INJURED','NUMBER OF CYCLIST KILLED','NUMBER OF MOTORIST INJURED',
        'NUMBER OF MOTORIST KILLED','CONTRIBUTING FACTOR VEHICLE 1','CONTRIBUTING FACTOR VEHICLE 2',
        'CONTRIBUTING FACTOR VEHICLE 3','CONTRIBUTING FACTOR VEHICLE 4','CONTRIBUTING FACTOR VEHICLE 5',
        'UNIQUE KEY','VEHICLE TYPE CODE 10','VEHICLE TYPE CODE 2','VEHICLE TYPE CODE 3',
        'VEHICLE TYPE CODE 4','VEHICLE TYPE CODE 5'
    ]
    sortedInput = list(data.columns)
    sortedInput.sort()
    VALUES.sort()
    if (VALUES != sortedInput):
        added = set(sortedInput).difference(VALUES)
        removed = set(VALUES).difference(sortedInput)
        logging.error('Inconsistency found...')
        if (len(added) != 0):
            logging.error('New columns added to the dataset: ' + str(added) + '.')
        if (len(removed) != 0):
            logging.error('Columns removed from the dataset: ' + str(removed) + '.')
        errors = True
    return errors

def main():
    errors = False
    init()
    logging.info('Running Tests...')
    df = readCSV()
    checkColumns(df)

main()