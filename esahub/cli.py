#!/usr/bin/env python
# coding=utf-8
""" This is the command line tool for the esahub python package.
"""
from __future__ import print_function
import locale
import warnings
import sys
import argparse
import time
import logging
import datetime
from .config import CONFIG


locale.setlocale(locale.LC_ALL, '')
warnings.filterwarnings("ignore",
                        message="WARNING: unsupported Compound type, skipping")
logger = logging.getLogger('esahub')


# -----------------------------------------------------------------------------
# PARSING COMMAND LINE OPTIONS
# -----------------------------------------------------------------------------
def parse_cli_options(args=None):
    """ Dedicated function for parsing command line options for esahub.
        An array of CLI arguments can be passed to simulate this behavior.
    """

    parser = argparse.ArgumentParser(
        description='Download satellite data archives.',
        formatter_class=lambda prog: argparse.RawTextHelpFormatter(
                prog, max_help_position=40))

    subparsers = parser.add_subparsers(help='sub-command help', dest='cmd')
    subparsers.required = True

    # Prepare different program streams:
    parser_get = subparsers.add_parser(
        'get', description='Download satellite data archives.',
        help='Download Sentinel data. \n  Type esahub get --help for details.',
        formatter_class=lambda prog: argparse.RawTextHelpFormatter(
                prog, max_help_position=40))

    parser_ls = subparsers.add_parser(
        'ls', description='Query satellite data archives for size.',
        help="Investigate the amount of available data.\n"
             "  Type esahub ls --help for details.",
        formatter_class=lambda prog: argparse.RawTextHelpFormatter(
                prog, max_help_position=40))

    parser_doctor = subparsers.add_parser(
        'doctor', description='Check local data for corruption.',
        help="Check already downloaded archives for consistency.\n"
             "  Type esahub doctor --help for details.",
        formatter_class=lambda prog: argparse.RawTextHelpFormatter(
                prog, max_help_position=40))

    # ARGUMENTS FOR ALL COMMANDS
    # -------------------------------------------------------------------------
    for p in (parser_get, parser_ls, parser_doctor):
        p.add_argument('-N', '--nproc', type=int,
                       help='Number of simultaneous processes/downloads.')
        p.add_argument('--log', action='store_true',
                       help='Write a log file.')
        p.add_argument('--debug', action='store_true',
                       help='Enable debugging.')
        p.add_argument('--email', action='store_true',
                       help='Send an email report.')
        p.add_argument('--gui', action='store_true',
                       help='Use GUI.')

    # ARGUMENTS FOR GET AND DOCTOR
    # -------------------------------------------------------------------------
    for p in (parser_get, parser_doctor):
        p.add_argument('-d', '--dir',
                       help='Specify the local data directory.')

    # ARGUMENTS FOR GET AND LS
    # -------------------------------------------------------------------------
    for p in (parser_get, parser_ls):
        p.add_argument(
            'sat', nargs='?', default=None,
            choices=list(CONFIG['SATELLITES'].keys()),
            help='Satellite')
        p.add_argument(
            '--mission',
            help="Select the mission (Sentinel-1, Sentinel-2, Sentinel-3).")
        p.add_argument(
            '--type',
            help="Select products matching specified product type (e.g. GRD).")
        p.add_argument(
            '--server', choices=list(CONFIG['SERVERS'].keys()),
            help="Specify the dowload server.")
        p.add_argument(
            '-g', '--geo', action='append',
            help="Specify geospatial location for intersection as point "
                 "or polygon. You can add multiple options.\n"
                 "  Examples: 'POINT(-6.26 53.35)' (Dublin) \n"
                 "  'POLYGON((-25.1 46.8,-5.25 46.8,-5.25 57.4,"
                 "-25.1 57.4,-25.1 46.8))' (Real Ireland)")
        p.add_argument(
            '--location', action='append',
            choices=[l for l, value in CONFIG['LOCATIONS'].items()],
            help="Specify location semantically as defined in config "
                 "file. You can add multiple options.\n"
                 "  Examples: 'Ireland_Mace_Head'")
        p.add_argument(
            '-t', '--time'
            help="Shortcuts for specifying time intervals. "
                 "Pass any date or date range in string format.\n"
                 "Special options include:\n"
                 "  today|yesterday|24h|midnight")
        p.add_argument(
            '-q', '--query', help='Specify custom query.')

    # ARGUMENTS FOR GET ONLY
    # -------------------------------------------------------------------------
    for p in (parser_get,):
        p.add_argument(
            '--force', action='store_true',
            help='Force download even if index existing.')
        p.add_argument(
            '--in', help='Read download list from file.')

    # ARGUMENTS FOR LS ONLY
    # -------------------------------------------------------------------------
    for p in (parser_ls,):
        p.add_argument(
            '--out', help='Write list to file.')

    # ARGUMENTS FOR DOCTOR ONLY
    # -------------------------------------------------------------------------
    for p in (parser_doctor,):
        p.add_argument(
            '-m', '--mode',
            help="Specify the mode for file checking. Options include:\n"
                 "  file - check if archives are valid zip or "
                 "netcdf files (very fast).\n"
                 "  md5 - check if archives match MD5 sum provided online "
                 "(can be slow).")
        p.add_argument(
            '--repair', action='store_true',
            help='Redownload corrupt files.')
        p.add_argument(
            '--delete', action='store_true',
            help='Delete corrupt files. Ignored if running with --repair')

    if args is None:
        return vars(parser.parse_args())
    else:
        return vars(parser.parse_args(args))


# -----------------------------------------------------------------------------
def not_none(dictionary, key):
    return (key in dictionary and dictionary[key] is not None)


def set_config(args):
    global CONFIG
    if not_none(args, 'mode'):
        CONFIG['GENERAL']['CHECK_MODE'] = args['mode']
    if not_none(args, 'force'):
        CONFIG['GENERAL']['SKIP_EXISTING'] = not args['force']
    if not_none(args, 'nproc'):
        CONFIG['GENERAL']['N_DOWNLOADS'] = \
            CONFIG['GENERAL']['N_PROC'] = args['nproc']
    # if not_none(args, 'quiet'):
    #     CONFIG['GENERAL']['QUIET'] = args['quiet']
    if not_none(args, 'dir'):
        CONFIG['GENERAL']['TMP_DIR'] = args['dir']
    if not_none(args, 'target'):
        CONFIG['GENERAL']['DATA_DIR'] = args['target']
    if not_none(args, 'output'):
        CONFIG['GENERAL']['SOLR_INDEX_FILE'] = args['output']
    if not_none(args, 'email'):
        CONFIG['GENERAL']['SEND_EMAIL'] = args['email']
    if not_none(args, 'log'):
        CONFIG['GENERAL']['LOGGING'] = args['log']
    if not_none(args, 'gui'):
        CONFIG['GENERAL']['USE_GUI'] = args['gui']

    if not_none(args, 'sat'):
        CONFIG['GENERAL']['QUERY']['satellite'] = args['sat']
    if not_none(args, 'server'):
        CONFIG['GENERAL']['QUERY']['server'] = args['server']
    if not_none(args, 'mission'):
        CONFIG['GENERAL']['QUERY']['mission'] = args['mission']
    if not_none(args, 'geo'):
        CONFIG['GENERAL']['QUERY']['geo'] = args['geo']
    if not_none(args, 'location'):
        CONFIG['GENERAL']['QUERY']['location'] = args['location']
    if not_none(args, 'time'):
        CONFIG['GENERAL']['QUERY']['time'] = args['time']
    if not_none(args, 'type'):
        CONFIG['GENERAL']['QUERY']['type'] = args['type']
    if not_none(args, 'query'):
        CONFIG['GENERAL']['QUERY']['query'] = args['query']

    if not_none(args, 'in'):
        CONFIG['GENERAL']['IN_FILE'] = args['in']
    if not_none(args, 'out'):
        CONFIG['GENERAL']['OUT_FILE'] = args['out']


# -----------------------------------------------------------------------------
def shutdown():
    from esahub import tty
    msg = 'Execution interrupted manually.'
    logger.warning(msg)
    tty.quit()
    print(msg, file=sys.stderr)
    sys.exit()


def main():
    """ Execute selected command. """
    args = parse_cli_options()
    set_config(args)
    cmd = args['cmd']

    # This needs to happen before logging is enabled!
    CONFIG['GENERAL']['LOG_FILE'] = CONFIG['GENERAL']['LOG_FILE'].format(
        cmd=cmd,
        time=datetime.datetime.strftime(datetime.datetime.now(),
                                        '%Y-%m-%d_%H-%M-%S')
    )
    CONFIG['GENERAL']['EMAIL_SUBJECT'] = \
        CONFIG['GENERAL']['EMAIL_SUBJECT'].format(cmd=cmd)

    if CONFIG['GENERAL']['SEND_EMAIL']:
        CONFIG['GENERAL']['LOGGING'] = True

    if CONFIG['GENERAL']['LOGGING'] or args['debug']:
        logging.basicConfig(
            filename=CONFIG['GENERAL']['LOG_FILE'],
            format='[%(asctime)s] %(levelname)s - %(message)s',
            datefmt='%m/%d/%Y %H:%M:%S',
            level=logging.DEBUG if args['debug'] else logging.INFO
        )
    else:
        logging.disable(logging.CRITICAL)

    program = 'esahub {}'.format(' '.join(sys.argv[1:]))
    logger.info('Executing: {}'.format(program))

    #
    # These modules MUST be imported AFTER altering the CONFIG.
    #
    from esahub import tty, main

    try:
        a = time.time()

        tty.init()
        if CONFIG['GENERAL']['USE_GUI']:
            tty.header(program)

        if cmd == 'doctor':
            main.doctor(delete=args['delete'], repair=args['repair'])

        elif cmd == 'ls':
            main.ls()

        elif cmd == 'get':
            main.get()

    except KeyboardInterrupt:
        shutdown()

    finally:
        b = time.time()
        logger.info('TOTAL EXECUTION TIME: {0:.1f}s'.format(b-a))

    # Send email report.
    if CONFIG['GENERAL']['LOGGING'] and CONFIG['GENERAL']['SEND_EMAIL'] and \
            len(CONFIG['GENERAL']['EMAIL_REPORT_RECIPIENTS']):
        main.email()

    if CONFIG['GENERAL']['USE_GUI']:
        try:
            tty.wait_for_quit()
        except KeyboardInterrupt:
            shutdown()


if __name__ == '__main__':
    main()
