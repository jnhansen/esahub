from esahub import config, utils, scihub
import os
import sys
import shutil

# -----------------------------------------------------------------------------
# TEST CONFIGURATION
# -----------------------------------------------------------------------------

#
# WARNING: Make sure the content of the following directories can be safely
# deleted!
# If they don't exist, they will be created.
#
TEST_DATA_DIR_ORIGINAL = 'esahub/tests/data/original/'
TEST_DATA_DIR_CORRUPT = 'esahub/tests/data/corrupt/'
TEST_DATA_DIR_TMP = 'esahub/tests/data/tmp/'


def _corrupt_binary(path):
    with open(path, 'wb') as f:
        f.write(b'78sadb')


def prepare():
    #
    # Create data directory structure
    #
    for d in (TEST_DATA_DIR_ORIGINAL, TEST_DATA_DIR_CORRUPT,
              TEST_DATA_DIR_TMP, ):
        if not os.path.exists(d):
            os.makedirs(d)
    #
    # Download test data
    #
    query = {'query': 'size: ???.* KB',
             'sort': ('size', 'asc'),
             'server': 'all'}
    fs = scihub.search(query, limit=2)
    _config = config.CONFIG['GENERAL']['DATA_DIR']
    config.CONFIG['GENERAL']['DATA_DIR'] = TEST_DATA_DIR_ORIGINAL
    scihub.download(fs)
    # move and corrupt one of the files
    corrupt_file = os.listdir(TEST_DATA_DIR_ORIGINAL)[-1]
    _move_from = os.path.join(TEST_DATA_DIR_ORIGINAL, corrupt_file)
    _move_to = os.path.join(TEST_DATA_DIR_CORRUPT, corrupt_file)
    shutil.move(_move_from, _move_to)
    _corrupt_binary(_move_to)
    config.CONFIG['GENERAL']['DATA_DIR'] = _config


def cleanup():
    clear_dirs = [TEST_DATA_DIR_ORIGINAL, TEST_DATA_DIR_CORRUPT]
    for d in clear_dirs:
        # Safety check
        if 'test' not in d:
            print('EXITING')
            sys.exit()

        # Delete all files in the directory
        for f in os.listdir(d):
            os.remove(os.path.join(d, f))


def set_test_config():
    # logging.disable(logging.CRITICAL)
    # Overwrite custom settings in ~/.esahub.conf
    config.load('esahub/config.yaml')
    config.CONFIG['GENERAL']['QUIET'] = True
    config.CONFIG['GENERAL']['DATA_DIR'] = TEST_DATA_DIR_TMP
    config.CONFIG['GENERAL']['TIMEOUT'] = 10.0
    config.CONFIG['GENERAL']['RECONNECT_TIME'] = 0.0
    config.CONFIG['GENERAL']['TRIALS'] = 3
    config.CONFIG['GENERAL']['WAIT_ON_503'] = False


def copy_test_data():
    for f in utils.ls(TEST_DATA_DIR_ORIGINAL):
        target = os.path.join(config.CONFIG['GENERAL']['DATA_DIR'],
                              os.path.split(f)[1])
        shutil.copy2(f, target)


def copy_corrupt_data():
    for f in utils.ls(TEST_DATA_DIR_CORRUPT):
        target = os.path.join(config.CONFIG['GENERAL']['DATA_DIR'],
                              os.path.split(f)[1])
        shutil.copy2(f, target)


def clear_test_data(tmp_only=False):
    clear_dirs = [config.CONFIG['GENERAL']['DATA_DIR']]
    for d in clear_dirs:
        # Safety check
        if 'test' not in d:
            print('EXITING')
            sys.exit()

        # Delete all files in the directory
        for f in os.listdir(d):
            os.remove(os.path.join(d, f))


def clear_all():
    clear_test_data()
