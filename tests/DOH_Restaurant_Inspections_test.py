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
    return pd.read_csv('restaurants.csv.gz', dtype = 'object')

def fixIndeces(data):
    # Adding underscores in all column names
    data.columns = data.columns.map(lambda x: x.replace(' ', '_'))

def checkColumns(data):
    errors = False
    logging.info('***Checking if any columns have benn removed or added to the dataset.***')
    # Check if all columns needed are in the dataset
    VALUES = ['INSPECTION_TYPE','CUISINE_DESCRIPTION','INSPECTION_DATE',
    'ACTION','SCORE','RECORD_DATE','GRADE','GRADE_DATE','VIOLATION_CODE',
    'BORO','BUILDING','STREET','CRITICAL_FLAG','VIOLATION_DESCRIPTION',
    'CAMIS', 'DBA', 'ZIPCODE', 'PHONE', 'Latitude', 'Longitude','Community_Board', 
    'Council_District', 'Census_Tract', 'BIN', 'BBL','NTA']
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
    logging.info('***Check the validity of the values of the dataset we use***')
    testVals = ['Cycle Inspection / Initial Inspection', 'Cycle Inspection / Re-inspection']
    errors |= testValues(data, 'INSPECTION_TYPE', testVals)
    testVals = [
        'Violations were cited in the following area(s).',
        'No violations were recorded at the time of this inspection.',
        'Establishment Closed by DOHMH.  Violations were cited in the following area(s) and those requiring immediate action were addressed.',
        'Establishment re-opened by DOHMH',
        'Establishment re-closed by DOHMH'
    ]
    errors |= testValues(data, 'ACTION', testVals)
    testVals = ['A', 'B', 'C', 'G']
    errors |= testValues(data, 'GRADE', testVals)

    errors |= testDates(data, 'INSPECTION_DATE')
    errors |= testDates(data, 'RECORD_DATE')
    errors |= testDates(data, 'GRADE_DATE')
    return errors
    
def testColumn(data, column):
    if not column in data.columns:
        logging.error('Inconsistency found...')  
        logging.error('Column %s does not exists' % (column))
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

def testValues(data, column, values):
    logging.info('Checking values on column %s' % column)
    if testColumn(data, column):
        return True
    
    inspVals = data[column].values
    for tval in values:
        if not tval in inspVals:
            logging.error('Inconsistency found...')  
            logging.error('Value %s is not in column %s' % (tval, column))
            error = True
    return False

def main():
    errors = False
    logging.info('Running Tests...')
    init()
    df = readCSV()
    fixIndeces(df)
    errors |= checkColumns(df)
    errors |= checkValues(df)
    if errors:
        logging.error('Errors found.')
        logging.info('Exiting with error code 1.')
        exit(1)
    logging.info('No errors found.')
    logging.info('Exiting...')
main()