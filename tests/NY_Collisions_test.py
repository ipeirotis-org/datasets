import pandas as pd
import logging

def init():
    # configure logging
    logger = logging.getLogger()
    handler = logging.FileHandler('.log','w')
    formatter = logging.Formatter('[%(asctime)s] %(levelname)-8s %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

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

def checkValues(data):
    errors = False
    errors |= testDates(data, 'DATE')
    errors |= testTime(data, 'TIME')

def testColumn(data, column):
    if not column in data.columns:
        logging.error('Inconsistency found...')
        logging.error('Column %s does not exists' % (column))
        return True
    return False

def testTime(data, column):
    logging.info('Checking time on column %s' % column)
    if testColumn(data, column):
        return True

    try:
        data[column] = pd.to_datetime(data[column], format='%H:%M')
    except ValueError:
        logging.error('Inconsistency found...')
        logging.error('There are malformed time values in column %s' % (column))
        return True
    return False

def testDates(data, column):
    logging.info('Checking dates on column %s' % column)
    if testColumn(data, column):
        return True

    try:
        data[column] = pd.to_datetime(data[column], format='%m/%d/%Y')
    except ValueError:
        logging.error('Inconsistency found...')
        logging.error('There are malformed date values in column %s' % (column))
        return True
    return False

def main():
    init()
    logging.info('Running Tests...')
    df = readCSV()
    errors = checkColumns(df)
    if errors:
        logging.error('Errors found.')
        logging.info('Exiting with error code 1.')
        exit(1)
    logging.info('No errors found.')
    logging.info('Exiting...')

main()