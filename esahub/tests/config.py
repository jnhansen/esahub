from esahub import config
from esahub import helpers
import os
import sys
import shutil

# -----------------------------------------------------------------------------
# TEST CONFIGURATION
# -----------------------------------------------------------------------------

#
# If you want to test with different data files, just change the variable
# TEST_DATA_DIR_ORIGINAL
#
TEST_DATA_DIR_ORIGINAL = 'esahub/tests/data/original/'
TEST_DATA_DIR_CORRUPT = 'esahub/tests/data/corrupt/'
#
# WARNING: Make sure the content of the following two directories can be safely
# deleted!
# If these don't exist, they will be created.
#
TEST_DATA_DIR_TMP = 'esahub/tests/data/tmp/'
TEST_DATA_DIR_METADATA = 'esahub/tests/data/stripped/'


def prepare():
    #
    # Check that a Solr instance is running
    #
    # ...

    #
    # Check that the S3 bucket exists.
    #
    # ...

    for d in (TEST_DATA_DIR_TMP, TEST_DATA_DIR_METADATA):
        if not os.path.exists(d):
            os.makedirs(d)


def cleanup():
    pass


def set_test_config():
    # logging.disable(logging.CRITICAL)
    config.CONFIG['GENERAL']['QUIET'] = True
    config.CONFIG['GENERAL']['TMP_DIR'] = TEST_DATA_DIR_TMP
    config.CONFIG['GENERAL']['DATA_DIR'] = TEST_DATA_DIR_METADATA
    # config.CONFIG['GENERAL']['SOLR_CORE'] = 'EVDC_test'
    config.CONFIG['GENERAL']['TIMEOUT'] = 3.0
    config.CONFIG['GENERAL']['RECONNECT_TIME'] = 0.0
    config.CONFIG['GENERAL']['TRIALS'] = 1
    config.CONFIG['GENERAL']['WAIT_ON_503'] = False
    # config.CONFIG['GENERAL']['S3_CONFIG_FILE'] = '~/.s3cfg.wos'
    # for sat in config.CONFIG['SATELLITES']:
    #     config.CONFIG['SATELLITES'][sat]['bucket'] = 'evdctest'


def copy_test_data():
    for f in helpers.ls(TEST_DATA_DIR_ORIGINAL):
        target = os.path.join(config.CONFIG['GENERAL']['TMP_DIR'],
                              os.path.split(f)[1])
        shutil.copy2(f, target)


def copy_corrupt_data():
    for f in helpers.ls(TEST_DATA_DIR_CORRUPT):
        target = os.path.join(config.CONFIG['GENERAL']['TMP_DIR'],
                              os.path.split(f)[1])
        shutil.copy2(f, target)


def clear_test_data(tmp_only=False):
    if tmp_only:
        clear_dirs = [config.CONFIG['GENERAL']['TMP_DIR']]
    else:
        clear_dirs = [config.CONFIG['GENERAL']['TMP_DIR'],
                      config.CONFIG['GENERAL']['DATA_DIR']]
    for d in clear_dirs:
        # Safety check
        if 'test' not in d:
            print('EXITING')
            sys.exit()

        # Delete all files in the directory
        for f in os.listdir(d):
            os.remove(os.path.join(d, f))


# def clear_test_index():
#     # Safety check
#     if not 'test' in index.CONFIG['GENERAL']['SOLR_CORE']:
#         print('EXITING')
#         sys.exit()

#     # Delete all documents from the Solr index
#     index._wipe()


# def clear_test_bucket():
#     # Safety check -- only proceed to do anything else if the S3 bucket
#     # contains 'test'
#     for sat in storage.CONFIG['SATELLITES']:
#         if 'test' not in storage.CONFIG['SATELLITES'][sat]['bucket']:
#             print('EXITING')
#             sys.exit()

#     # Delete all files in S3 bucket:
#     for s3_obj in storage.ls():
#         storage.delete(s3_obj['name'])


def clear_all():
    clear_test_data()
    # clear_test_index()
    # clear_test_bucket()
