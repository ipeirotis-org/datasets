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
    return pd.read_csv('nypd.csv', dtype = 'object')

def checkColumns(data):
    errors = False
    logging.info('***Checking if any columns have benn removed or added to the dataset.***')
    # Check if all columns needed are in the dataset
    VALUES = [
        'CMPLNT_NUM','CMPLNT_FR_DT','CMPLNT_FR_TM','CMPLNT_TO_DT','CMPLNT_TO_TM',
        'ADDR_PCT_CD','RPT_DT','KY_CD','OFNS_DESC','PD_CD','PD_DESC','CRM_ATPT_CPTD_CD',
        'LAW_CAT_CD','BORO_NM','LOC_OF_OCCUR_DESC','PREM_TYP_DESC','JURIS_DESC',
        'JURISDICTION_CODE','PARKS_NM','HADEVELOPT','HOUSING_PSA','X_COORD_CD',
        'Y_COORD_CD','SUSP_AGE_GROUP','SUSP_RACE','SUSP_SEX','TRANSIT_DISTRICT',
        'Latitude','Longitude','Lat_Lon','PATROL_BORO','STATION_NAME','VIC_AGE_GROUP',
        'VIC_RACE','VIC_SEX'
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
    logging.info('***Check the validity of the values of the dataset we use***')
    testVals = ['<18', '18-24',  '25-44', '45-64', '65+']
    errors |= testValues(data, 'VIC_AGE_GROUP', testVals)
    errors |= testValues(data, 'SUSP_AGE_GROUP', testVals)

    errors |= testDates(data, 'CMPLNT_TO_DT')
    errors |= testDates(data, 'CMPLNT_FR_DT')
    errors |= testDates(data, 'RPT_DT')

    errors |= testTime(data, 'CMPLNT_TO_TM')
    errors |= testTime(data, 'CMPLNT_FR_TM')
    return errors

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
        data[column] = pd.to_datetime(data[column], format='%H:%M:%S')
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
    init()
    logging.info('Running Tests...')
    df = readCSV()
    errors |= checkColumns(df)
    errors |= checkValues(df)
    if errors:
        logging.error('Errors found.')
        logging.info('Exiting with error code 1.')
        exit(1)
    logging.info('No errors found.')
    logging.info('Exiting...')

main()