# coding=utf-8
""" This module implements the main commands accessible from the command line.
"""
from __future__ import print_function
import subprocess
import logging
import sys
import os
import json
import multiprocessing
from functools import partial
from .config import CONFIG
from . import scihub, check, tty, helpers

logger = logging.getLogger('esahub')
PY2 = sys.version_info < (3, 0)


# -----------------------------------------------------------------------------
# HELPER FUNCTIONS
# -----------------------------------------------------------------------------
def list_local_archives():
    #
    # Collect a list of all files.
    #
    return helpers.ls(CONFIG['GENERAL']['DATA_DIR'])


# -----------------------------------------------------------------------------
# MAIN COMMANDS
# -----------------------------------------------------------------------------
def query_file_list(query=None, limit=None):
    if 'IN_FILE' in CONFIG['GENERAL'] and \
            CONFIG['GENERAL']['IN_FILE'] is not None:
        with open(CONFIG['GENERAL']['IN_FILE'], 'r') as f:
            file_list = json.load(f)
    else:
        if query is None:
            query = CONFIG['GENERAL']['QUERY']
        file_list = scihub.search(query, limit=limit)

    return file_list


def get(query=None, limit=None):
    """This method downloads the files found in a query.

    The main method in the script. Based on the specified command line options
    it queries the webserver, extracts all matching files and downloads them
    into the requested location.

    Parameters
    ----------
    query : dict, optional
        A Query object to restrict the files retrieved.
    limit : int, optional
        The maximum number of files to download.
    """
    file_list = query_file_list(query, limit=limit)
    size = sum(f['size'] for f in file_list)

    msg = 'Preparing {0:d} files ({1}) for download into {2} ...'.format(
        len(file_list),
        helpers.b2h(size),
        CONFIG['GENERAL']['DATA_DIR']
    )
    logging.info(msg)
    tty.status(msg)

    scihub.download_many(file_list)


def ls(query=None, quiet=False):
    """List and count files matching the query and compute total file size.

    Parameters
    ----------
    query : dict, optional
        (default: None)
    quiet : bool, optional
        Whether to suppress console output.
    """
    if query is None:
        query = CONFIG['GENERAL']['QUERY']
    file_list = scihub.search(query)
    size = 0.0
    for f in file_list:
        size += f['size']
    if not quiet:
        msg = 'Found {0:d} files ({1}).'.format(len(file_list),
                                                helpers.b2h(size))
        logging.info(msg)
        tty.result(msg)
        for f in file_list:
            msg = '{:>8} {}'.format(helpers.b2h(f['size']), f['filename'])
            # tty.update(f['filename'],msg)
            logging.info(f['filename'])

    #
    # Write file_list to JSON file
    # so it can be read later by the get() and store() commands.
    #
    if 'OUT_FILE' in CONFIG['GENERAL'] and \
            CONFIG['GENERAL']['OUT_FILE'] is not None:
        with open(CONFIG['GENERAL']['OUT_FILE'], 'w') as f:
            json.dump(file_list, f, default=str, indent=2)

    return file_list


def doctor(delete=False, repair=False):
    """Checks all files in directory for consistency and generates report.

    Parameters
    ----------
    delete : bool, optional
        Whether to delete corrupt files (default: False)
    reapir : bool, optional
        Whether to attempt a redownload of corrupt files (default: False)
    """
    check._init_bad_file_counter()
    all_files = list_local_archives()
    msg = 'Checking {:d} files for consistency (mode: {}).'.format(
            len(all_files), CONFIG['GENERAL']['CHECK_MODE'])
    logging.info(msg)
    tty.status(msg)

    #
    # Check every file in the list.
    #
    pool = multiprocessing.Pool(processes=CONFIG['GENERAL']['N_PROC'])
    partial_check_file = partial(check.check_file,
                                 mode=CONFIG['GENERAL']['CHECK_MODE'])
    for f in all_files:
        pool.apply_async(partial_check_file, args=(f,),
                         callback=check._register_bad_file)
    pool.close()
    pool.join()

    msg = '{0:d}/{1:d} files corrupt.'.format(check.BAD_FILE_COUNTER,
                                              len(all_files))
    logging.info(msg)
    tty.result(msg)

    if repair:
        tty.status('Redownloading {} corrupt files ...'.format(
                check.BAD_FILE_COUNTER))
        scihub.redownload(check.BAD_FILES)

    elif delete:
        tty.status('Deleting {} corrupt files ...'.format(
                check.BAD_FILE_COUNTER))
        for f in check.BAD_FILES:
            os.remove(f)
        msg = 'Deleted {} corrupt files!'.format(check.BAD_FILE_COUNTER)
        logging.info(msg)
        tty.result(msg)


def _product_file(f):
    product = os.path.split(f)[1]
    if product.endswith('.nc.zip'):
        product = os.path.splitext(product)[0]
    else:
        product = os.path.splitext(product)[0]
        sat = helpers.get_satellite(product)
        if sat in CONFIG['SATELLITES']:
            product += CONFIG['SATELLITES'][sat]['ext']
        else:
            product += '.zip'
    return product


def email():
    """Send an email report with the current log file.

    This method sends the current log file to the email recipients as specified
    in the config module. It is not meant to be called independently from the
    command line.
    """
    sender = CONFIG['GENERAL']['EMAIL_SENDER']
    recipients = CONFIG['GENERAL']['EMAIL_REPORT_RECIPIENTS']

    from email.mime.text import MIMEText
    with open(CONFIG['GENERAL']['LOG_FILE'], 'rb') as fp:
        log_content = fp.read()
        if not PY2:
            log_content = log_content.decode()
        message = MIMEText(log_content)

    message['Subject'] = CONFIG['GENERAL']['EMAIL_SUBJECT']
    message['From'] = sender
    message['To'] = ','.join(recipients)

    p = subprocess.Popen(
        ['/usr/sbin/sendmail', '-t'],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
    )
    if PY2:
        p.communicate(message.as_string())
    else:
        p.communicate(message.as_bytes())
