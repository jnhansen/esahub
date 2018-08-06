# coding=utf-8
""" This module implements the interface with the SciHub portal,
    especially authentication and queries.

TODO: Switch from multiprocessing to threading?

"""
import lxml.etree as ET
import os
import sys
import time
import logging
import re
import errno
# import hashlib
import base64
import ssl
# import math
import datetime as DT
import pytz
import multiprocessing
import socket
from functools import partial
from collections import OrderedDict
from .config import CONFIG
from . import helpers, tty, geo, checksum

logger = logging.getLogger('esahub')
PY2 = sys.version_info < (3, 0)

if PY2:
    # Python2 imports
    from urllib import urlencode
    from urllib2 import urlopen, Request
    from urllib2 import HTTPError, URLError
    from urlparse import urlparse, parse_qs
else:
    # Python3 imports
    from urllib.request import urlopen, Request
    from urllib.parse import urlparse, parse_qs, urlencode
    from urllib.error import HTTPError, URLError

COUNTER = 0
TOTAL = 0
COLLECT = []

DOWNLOAD_URL_PATTERN = \
    "{host}/odata/v1/Products('{uuid}')/$value"
CHECKSUM_URL_PATTERN = \
    "{host}/odata/v1/Products('{uuid}')/Checksum/Value/$value"
PREVIEW_URL_PATTERN = \
    "{host}/odata/v1/Products('{uuid}')/Products('Quicklook')/$value"


# -----------------------------------------------------------------------------
# CLASS DEFINITION: CONNECTION
# -----------------------------------------------------------------------------
class NotFoundError(Exception):
    pass


class Connection(object):
    """
    An abstraction of an authenticated connection to the Copernicus SciHub.
    """
    user = ''
    password = ''

    def __init__(self, mission=None, user=None, password=None, host=None):
        if mission is not None:
            self.authenticate(mission=mission)
        else:
            self.login(user=user, password=password, host=host)

    # @classmethod
    def login(self, user, password, host):
        """Define the login credentials.

        Parameters
        ----------
        user : str
        password : str
        host : str
            The URL to the SciHub host.
        """
        self.host = host
        self.user = user
        self.password = password

    # @classmethod
    def authenticate(self, mission):
        """Sets the login credentials as appropriate for the specified mission.

        Parameters
        ----------
        mission : {'S1A', 'S1B', 'S2A', 'S2B', 'S3A'}
        """
        if mission in CONFIG['SATELLITES']:
            source = CONFIG['SATELLITES'][mission]['source'][0]
            self.login(
                **CONFIG['SERVERS'][source]
            )
        else:
            logging.warning('No server found for mission: {}'.format(mission))

    # GENERAL METHODS FOR HTTP REQUESTS AND DOWNLOADS
    # -------------------------------------------------------------------------
    @classmethod
    def _encode(cls, url):
        """Minimal URL encoding as needed for this specific purpose.

        Parameters
        ----------
        url : str

        Returns
        -------
        str
            The encoded URL.
        """
        url = url.replace(' ', '%20')
        url = url.replace('"', '%22')
        return url

    # @classmethod
    def resolve(self, url):
        """Resolves the specified URL handling the HTTP authentication.

        Authenticates with the server and returns the urllib response object.
        Handles connection timeouts and 503 status codes as specified in the
        config module.

        Parameters
        ----------
        url : str

        Returns
        -------
        HTTP response
            Provides functions such as `read()`, `readline()`, `getcode()`,
            `geturl()`, `info()`

        """
        trials = 0
        while True:
            try:
                url = self._encode(url)
                request = Request(url)
                if not (self.user is None and self.password is None):
                    if PY2:
                        base64string = base64.b64encode('{}:{}'.format(
                                self.user, self.password))
                    else:
                        base64string = base64.b64encode('{}:{}'.format(
                                self.user, self.password
                            ).encode('ascii')).decode('ascii')
                    request.add_header("Authorization",
                                       "Basic {}".format(base64string))
                gcontext = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
                result = urlopen(request, timeout=CONFIG['GENERAL']['TIMEOUT'],
                                 context=gcontext)
            except socket.timeout as e:
                return HTTPError(url=url, code=504, msg='{}'.format(e),
                                 hdrs={}, fp='')
            except HTTPError as e:
                # print(e)
                # if CONFIG['GENERAL']['WAIT_ON_503'] and e.code == 503:
                #     time.sleep(CONFIG['GENERAL']['RECONNECT_TIME'])
                if CONFIG['GENERAL']['WAIT_ON_503']:
                    time.sleep(CONFIG['GENERAL']['RECONNECT_TIME'])
                else:
                    trials += 1
                    #
                    # If the connection could not be established after the
                    # maximum number of trials, raise with error message.
                    #
                    if trials >= CONFIG['GENERAL']['TRIALS']:
                        logging.error('{0} {1}, URL: {2}'.format(
                            tty.error('ERROR (%i trials):' % trials), e, url))
                        # raise
                        return e
                    #
                    # Wait for an increasing time after every trial.
                    #
                    time.sleep(CONFIG['GENERAL']['RECONNECT_TIME'] * trials)
            else:
                return result

    def auto_resolve(self, url):
        # Detect server from url:
        # host = re.search('(.*)/search', url).group(1)
        # auth = helpers.select(CONFIG['SERVERS'], first=True, host=host)
        auth = {}
        for servername, server in CONFIG['SERVERS'].items():
            if server['host'] in url:
                auth = server
                break
        # if len(auth) == 0:
        #     print(url)
        self.login(**auth)
        return self.resolve(url)


# -----------------------------------------------------------------------------
# NEW METHODS
# -----------------------------------------------------------------------------
def _generate_next_url(url, total=None):
    parsed_url = urlparse(url)
    q_params = parse_qs(parsed_url.query)
    q_params = {k: v[0] if len(v) == 1 else v for k, v in q_params.items()}
    if 'rows' in q_params:
        q_params['rows'] = int(q_params['rows'])
    else:
        q_params['rows'] = 10
    if 'start' in q_params:
        q_params['start'] = int(q_params['start'])
    else:
        q_params['start'] = 0
    q_params['start'] += q_params['rows']

    if total is None or q_params['start'] <= total:
        parsed_url = parsed_url._replace(query=urlencode(q_params, doseq=True))
        return parsed_url.geturl()
    else:
        return False


def _parse_page(url, first=False):
    file_list = []

    prefixes = {
        'os': 'http://a9.com/-/spec/opensearch/1.1/',
        'opensearch': 'http://a9.com/-/spec/opensearch/1.1/',
        'doc': 'http://www.w3.org/2005/Atom',
        'gml': 'http://www.opengis.net/gml'
    }

    #
    # Retrials are handled in the resolve method
    #
    conn = Connection()
    try:
        response = conn.auto_resolve(url)
        if isinstance(response, HTTPError):
            raise response
    except HTTPError:
        if first:
            return 0, []
        else:
            return []

    xml = response.read()
    try:
        root = ET.fromstring(xml)
        total_results = int(root.find('os:totalResults', prefixes).text)
        # next_link = root.find("./doc:link[@rel='next']", prefixes)
        for entry in root.findall('doc:entry', prefixes):

            filename = entry.find("./doc:str[@name='identifier']",
                                  prefixes).text
            ingestiondate = helpers.to_date(
                entry.find("./doc:date[@name='ingestiondate']", prefixes).text,
                output='date')
            try:
                footprint_tag = entry.find("./doc:str[@name='gmlfootprint']",
                                           prefixes).text
                match = re.search('<gml:coordinates>(.*)</gml:coordinates>',
                                  footprint_tag)
                coords = geo.gml_to_polygon(match.groups()[0])
            except AttributeError:
                coords = None

            filesize = helpers.h2b(entry.find("./doc:str[@name='size']",
                                              prefixes).text)
            preview_url = entry.find("./doc:link[@rel='icon']",
                                     prefixes).attrib['href']
            file_dict = {
                # 'position'  : file_counter,
                'title': entry.find('doc:title', prefixes).text,
                'url': entry.find('doc:link', prefixes).attrib['href'],
                'host': conn.host,
                'preview': preview_url,
                'uuid': entry.find('doc:id', prefixes).text,
                'filename': filename,
                'size': filesize,
                'ingestiondate': ingestiondate,
                'coords': coords
            }
            file_list.append(file_dict)

    except ET.XMLSyntaxError:
        # not valid XML
        total_results = 0
        file_list = []

    if first:
        return total_results, file_list
    else:
        return file_list


def _get_file_list_from_url(url, limit=None):
    global COUNTER, TOTAL, COLLECT
    """ This function returns a list of all files resulting from the specified
    query.

    This method executes the query defined by the passed URL. It automatically
    takes care of the pagination implemented by SciHub and iterates over the
    returned pages.

    Parameters
    ----------
    query_url : str
        The SciHub URL that constitutes the query. It can be built using
        `Query.build_query_url()`
    limit : int, optional
        The maximum number of results to return. If `None`, return all results
        (default: None).

    Returns
    -------
    list of dict
        A list of dictionaries containing metadata for each found file. Each
        dictionary contains the following keys:
        `position`, `title`, `url`, `preview`, `id`, `filename`, `size`,
        `coords`
    """
    # file_list = []
    # file_counter = 0
    total_results = 0
    # TOTAL_SIZE = 0.0

    logging.debug('QUERYING {0} ...'.format(url))
    urlname = urlparse(url).netloc

    #
    # Parallel parsing of pages.
    #

    # Parse first page serially to get total number of results.
    current_url = url
    total_results, files_first_page = _parse_page_wrapper(current_url,
                                                          first=True)
    if limit is None:
        TOTAL = total_results
    else:
        TOTAL = min(limit, total_results)

    COUNTER = 0
    COLLECT = []

    def _callback(result):
        global COUNTER, TOTAL, COLLECT
        COLLECT.extend(result)
        COUNTER += len(result)
        status = (0, 1) if TOTAL == 0 else (COUNTER, TOTAL)
        tty.status('Querying {}...'.format(urlname), progress=status)

    _callback(files_first_page)

    #
    # The processes are not CPU-intensive at all (the bottleneck is the server
    # response time), therefore we can handle very large number of processes.
    #
    pool = multiprocessing.Pool(
            processes=CONFIG['GENERAL']['N_SCIHUB_QUERIES'])

    while True:
        current_url = _generate_next_url(current_url, total=TOTAL)
        if not current_url:
            break
        pool.apply_async(_parse_page_wrapper, (current_url,),
                         callback=_callback)

    pool.close()
    pool.join()
    tty.finish_status()

    if limit is not None:
        COLLECT = COLLECT[:limit]

    # from IPython import embed; embed()

    # TOTAL_SIZE = sum([f['size'] for f in COLLECT])

    return COLLECT


def _parse_page_wrapper(*args, **kwargs):
    #
    # For some weird reason, _parse_page sometimes raises:
    #      AttributeError: 'str' object has no attribute 'close'
    # from the tempfile module. As this only occurs sometimes,
    # just try again ...
    #
    while True:
        try:
            result = _parse_page(*args, **kwargs)
        except Exception as e:
            time.sleep(1)
        else:
            return result


def _build_query(query={}):
    """ Builds and returns the query URL given the command line input
    parameters.

    Parameters
    ----------
    query : list, optional
        A list of additional custom query elements submitted to SciHub. The
        queries will be concatenated with ampersands (&).
    """
    query_list = []
    sort_string = ''

    # Default ingestiontime query parameters
    start = '1970-01-01T00:00:00.000Z'
    end = 'NOW'
    # Geospatial query list
    geo_query_list = []

    for key, val in query.items():
        if key == 'mission':
            # Build mission selection query:
            query_list.append('platformname:{0}'.format(query['mission']))

        elif key == 'satellite':
            # Build satellite selection query:
            query_list.append('identifier:{0}*'.format(query['satellite']))

        elif key == 'from_time':
            start = query['from_time']
        elif key == 'to_time':
            end = query['to_time']

        elif key == 'time':
            if val == 'today':
                start = DT.datetime.strftime(DT.datetime.now(pytz.utc),
                                             '%Y-%m-%dT00:00:00.000Z')
            elif val == 'yesterday':
                start = DT.datetime.strftime(DT.datetime.now(pytz.utc)
                                             - DT.timedelta(1),
                                             '%Y-%m-%dT00:00:00.000Z')
                end = DT.datetime.strftime(DT.datetime.now(pytz.utc),
                                           '%Y-%m-%dT00:00:00.000Z')
            elif val == 'midnight':
                end = DT.datetime.strftime(DT.datetime.now(pytz.utc),
                                           '%Y-%m-%dT00:00:00.000Z')
            elif val == '24h':
                start = DT.datetime.strftime(DT.datetime.now(pytz.utc)
                                             - DT.timedelta(1),
                                             '%Y-%m-%dT%H:%M:%S.000Z')
                start = DT.datetime.strftime(DT.datetime.now(pytz.utc),
                                             '%Y-%m-%dT%H:%M:%S.000Z')

        elif key == 'geo':
            # Build geospatial query:
            if type(val) is not list:
                val = [val]
            for item in val:
                geo_query_list.append(
                        'footprint:"Intersects({0})"'.format(item))

        elif key == 'location':
            if type(val) is not list:
                val = [val]
            for loc in val:
                if loc in CONFIG['LOCATIONS']:
                    geo_query_list.append('footprint:"Intersects({0})"'.format(
                            CONFIG['LOCATIONS'][loc]))
                else:
                    logging.error(
                        '{0} {1}'.format(tty.error('Location not found:'), loc)
                    )

        elif key == 'type':
            query_list.append('producttype:{0}'.format(query['type']))

        elif key == 'query':
            query_list.append('{0}'.format(query['query']))

        elif key == 'sort':
            sort_string = '&orderby={} {}'.format(*query['sort'])

        # Not a special keyword. Pass directly to SciHub
        else:
            query_list.append('{}:{}'.format(key, val))

    # Build ingestiondate query:
    query_list.append('ingestiondate:[{0} TO {1}]'.format(start, end))

    # Build geospatial query:
    if len(geo_query_list):
        query_list.append(
            '({})'.format(' OR '.join(geo_query_list))
        )

    # Generate full query string
    if len(query_list) == 0:
        query_list.append('*:*')
    query_string = ' AND '.join(query_list)

    #
    # Example: 'https://scihub.copernicus.eu/s3/search?
    #           q=(footprint:"Intersects(POLYGON((-25.100 46.800,
    #           -5.250 46.800,-5.250 57.400,-25.100 57.400,-25.100 46.800)))")
    #           &rows=25&start=0'
    #
    query_url = 'q={q}&start=0&rows={rows}{sort}'.format(
        q=query_string,
        rows=CONFIG['GENERAL']['ENTRIES'],
        sort=sort_string
    )
    return query_url


def _build_url(query, server):
    if type(query) is dict:
        query_string = _build_query(query)
    else:
        query_string = query
    return '{url}/search?{q}'.format(
        url=CONFIG['SERVERS'][server]['host'], q=query_string
    )


def _download(url, destination, quiet=None, queue=None):
    """Downloads a file from the remote server into the specified destination.

    Parameters
    ----------
    url : str
        The source URL.
    destination : str
        The local target file path.
    quiet : bool, optional
        Whether to suppress any command line output.
    queue : multiprocessing.Manager.Queue, optional
        A multiprocessing queue to submit status messages.

    Returns
    -------
    bool
        True if successful, False otherwise.
    """
    quiet = CONFIG['GENERAL']['QUIET'] if quiet is None else quiet

    #
    # Create directory.
    #
    path, file_name = os.path.split(destination)
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise

    try:
        response = resolve(url)
        if PY2:
            size = int(response.info().getheaders("Content-Length")[0])
        else:
            size = int(response.headers.get("Content-Length"))
        # size_str = helpers.b2h(size)
        if queue is not None:
            queue.put((file_name, {'total': size,
                                   'desc': 'Downloading {name}'}))
        CHUNK = 32 * 1024
        chunks_done = 0
        t_start_download = time.time()
        with open(destination, 'wb') as f:
            while True:
                chunk = response.read(CHUNK)
                if not chunk:
                    break
                f.write(chunk)
                chunks_done += 1
                if queue is not None:
                    queue.put((file_name, {'progress': CHUNK}))
                    # if size is not None:
                    #     queue.put((file_name,
                    #                '{} Downloading ({} / {})'.format(
                    #                     file_name,
                    #                     helpers.b2h(chunks_done*CHUNK),
                    #                     size_str)
                    #                ))
                    # else:
                    #     queue.put((file_name, '{} Downloading ({})'.format(
                    #             file_name, helpers.b2h(chunks_done*CHUNK))))
        t_stop_download = time.time()
        download_size = os.path.getsize(destination)
        download_rate = download_size/(t_stop_download - t_start_download)
        msg = '{0} Downloaded ({1} at {2}/s)'.format(
            file_name, helpers.b2h(download_size), helpers.b2h(download_rate)
        )
        if not quiet:
            logging.info(msg)
        if queue is not None:
            queue.put((file_name, {'desc': '{name} Downloaded'}))
        #     queue.put((file_name, msg))

    except HTTPError as e:
        return False
    except URLError as e:
        return False
    except Exception as e:
        logging.error(repr(e))
        return False
    else:
        return True


# def _get_file_list_wrapper(url):
#     host = re.search('(.*)/search',url).group(1)
#     server = helpers.select(list(CONFIG['SERVERS'].values()), host=host)
#     if type(server) is list:
#         server = server[0]
#     Connection.login(**server)
#     return _get_file_list_from_url(url)


def _get_available_servers():
    servers = [server for server, conf in CONFIG['SERVERS'].items()
               if len(conf['user']) > 0 and len(conf['password']) > 0]
    return servers


def _ping_single(servername):
    # print('Pinging {} ...'.format(servername))
    server = CONFIG['SERVERS'][servername]
    conn = Connection(**server)
    try:
        result = conn.resolve('{url}/search?q=*:*'.format(url=server['host']))
        # results[servername] = result.status
        return (servername, result.status)
    except HTTPError as e:
        # results[servername] = e.status
        return (servername, e.status)


def _auto_detect_server_from_query(query, available_only=False):
    servers = None

    if 'satellite' in query and query['satellite'] in CONFIG['SATELLITES']:
        servers = CONFIG['SATELLITES'][query['satellite']]['source']

    if 'identifier' in query:
        sat = query['identifier'][:3]
        if sat in CONFIG['SATELLITES']:
            servers = CONFIG['SATELLITES'][sat]['source']

    if 'mission' in query:
        sats = helpers.select(CONFIG['SATELLITES'], platform=query['mission'])
        if len(sats) > 0:
            ll = [source for sat in sats.values() for source in sat['source']]
            servers = list(OrderedDict.fromkeys(ll))

    #
    # If the server couldn't be determined from the query, return a list of
    # all servers.
    #
    if servers is None:
        servers = list(CONFIG['SERVERS'].keys())

    if available_only:
        servers = [server for server in servers
                   if server in _get_available_servers()]

    return servers


def _uuid_from_identifier(identifier):
    identifier = os.path.splitext(os.path.split(identifier)[1])[0]
    results = search({'identifier': identifier+'*'})
    if len(results) == 0:
        raise NotFoundError('Product not found: {}'.format(identifier))
    return results[0]['uuid']


def _host_and_uuid_from_identifier(identifier):
    identifier = os.path.splitext(os.path.split(identifier)[1])[0]
    results = search({'identifier': identifier+'*'})
    if len(results) == 0:
        raise NotFoundError('Product not found: {}'.format(identifier))
    return (results[0]['host'], results[0]['uuid'])


def _host_from_uuid(uuid):
    #
    # IMPLEMENT THIS
    #
    return None


def _download_url_from_identifier(identifier):
    host, uuid = _host_and_uuid_from_identifier(identifier)
    return _download_url_from_uuid(uuid, host=host)


def _checksum_url_from_identifier(identifier):
    host, uuid = _host_and_uuid_from_identifier(identifier)
    return _checksum_url_from_uuid(uuid, host=host)


def _preview_url_from_identifier(identifier):
    host, uuid = _host_and_uuid_from_identifier(identifier)
    return _preview_url_from_uuid(uuid, host=host)


def _download_url_from_uuid(uuid, host=None):
    if host is None:
        host = _host_from_uuid(uuid)
    return DOWNLOAD_URL_PATTERN.format(host=host, uuid=uuid)


def _checksum_url_from_uuid(uuid, host=None):
    if host is None:
        host = _host_from_uuid(uuid)
    return CHECKSUM_URL_PATTERN.format(host=host, uuid=uuid)


def _preview_url_from_uuid(uuid, host=None):
    if host is None:
        host = _host_from_uuid(uuid)
    return PREVIEW_URL_PATTERN.format(host=host, uuid=uuid)


# -----------------------------------------------------------------------------
# API METHODS
# -----------------------------------------------------------------------------
def resolve(url, server=None):
    """ Resolves a SciHub URL and automatically determines the correct HTTP
    authentication.

    Parameters
    ----------
    url : str
        The URL to resolve.
    server : str, optional
        If specified, resolve using the specified server. Not in general
        needed.

    Returns
    -------
    HTTPResponse
        The HTTPRessponse or HTTPError object resulting from the URL.
    """
    if server is None:
        if 'server' in CONFIG['GENERAL']['QUERY']:
            auth = CONFIG['SERVERS'][CONFIG['GENERAL']['QUERY']['server']]
            conn = Connection(**auth)
            return conn.resolve(url)
        else:
            conn = Connection()
            return conn.auto_resolve(url)
    else:
        auth = CONFIG['SERVERS'][server]
        conn = Connection(**auth)
        return conn.resolve(url)


def ping(server=None):
    results = {}
    if server is not None:
        servers = [server]
    else:
        servers = list(CONFIG['SERVERS'].keys())

    pool = multiprocessing.Pool(processes=len(servers))
    results = pool.map_async(_ping_single, servers)
    # pool.close()
    # pool.join()
    # for servername,server in servers.items():
    while not results.ready():
        time.sleep(1)
    return results.get()


def search(query={}, server='auto', limit=None, **kwargs):
    """ Search SciHub for satellite products.
    Parameters
    ----------
    query : dict, optional
        Query parameters as dictionary. May contain key 'server' (see below).
    server : str, optional
        If server is 'all', search all saved SciHub servers.
        If server is 'auto', attempt to auto-detect the server from the query.
        Otherwise, use the specified server (as configured in CONFIG.SERVERS)
        (default: 'auto')
    limit : int, optional
        The maximum number of results to return.
    kwargs : dict, optional
        The query parameters can also be passed as keyword arguments.

    Returns
    -------
    list of dict
        A list of dictionaries representing the found search results.
    """
    #
    # Search in each server.
    #
    query.update(kwargs)
    if 'server' in query:
        server = query.pop('server')

    if server == 'all':
        servers = _get_available_servers()
    elif server == 'auto':
        servers = _auto_detect_server_from_query(query, available_only=True)
    else:
        servers = [server]

    if servers is None:
        servers = []
    results = []
    query_string = _build_query(query)

    remaining = limit
    for servername in servers:
        server = CONFIG['SERVERS'][servername]
        # Connection.login(**server)
        url = '{url}/search?{q}'.format(
            url=server['host'], q=query_string
        )
        logging.debug('Trying server {}: {}'.format(servername, url))
        results.extend(_get_file_list_from_url(url, limit=remaining))
        if remaining is not None:
            remaining = limit - len(results)
            if remaining <= 0:
                break

    #
    # Delete duplicate results (if product is on multiple servers).
    #
    filtered = OrderedDict(zip([_['filename'] for _ in results], results))
    return list(filtered.values())


# def remote_md5(query_url):
#     """Returns the md5 sum of the file stored on SciHub given the download
#     URL.
#
#     Parameters
#     ----------
#     query_url : str
#         The SciHub download URL.
#
#     Returns
#     -------
#     str
#         The md5 checksum in lower case.
#     """
#
#     md5_query_url = query_url.replace('/$value','/Checksum/Value/$value')
#     response = Connection.resolve(md5_query_url)
#     if PY2:
#         return response.read().lower()
#     else:
#         return response.read().decode().lower()


def md5(product=None, uuid=None):
    """Returns the md5 sum of the file stored on SciHub given the product name
    or uuid.

    Parameters
    ----------
    product : str, optional
        The product name. If given, `uuid` is ignored.
    uuid : str, optional
        The product uuid.

    Returns
    -------
    str
        The md5 checksum in lower case.
    """
    if product is not None:
        if type(product) is dict and 'uuid' in product and 'host' in product:
            md5_url = _checksum_url_from_uuid(product['uuid'],
                                              host=product['host'])
        elif type(product) is str:
            md5_url = _checksum_url_from_identifier(product)
        else:
            return False

    elif uuid is not None:
        md5_url = _checksum_url_from_uuid(uuid)

    response = resolve(md5_url)
    if PY2:
        return response.read().lower()
    else:
        return response.read().decode().lower()


def exists(product):
    search_results = search({'identifier': product+'*'}, limit=1)
    return len(search_results) > 0


def download(product, queue=None, stopqueue=True):
    """Download a satellite product.

    Checks for file existence and MD5 checksum.

    Parameters
    ----------
    product : str or dict
        The name of the product to be downloaded from SciHub.
        Alternatively, a dictionary representing a search result from SciHub.
    queue : multiprocessing.Manager.Queue, optional
        A multiprocessing queue to submit status messages.
    stopqueue : bool, optional
        Whether to send a poison pill upon completion.

    Returns
    -------
    str
        The local file path if the download was successful OR the file already
        exists and passes the md5 checksum test. False otherwise.
    """
    if type(product) is dict:
        fdata = product
    else:
        fdata = search({'identifier': os.path.splitext(product)[0]+'*'})[0]

    satellite = helpers.get_satellite(fdata['filename'])
    ext = CONFIG['SATELLITES'][satellite]['ext']
    # suffix = CONFIG['SATELLITES'][satellite]['suffix']
    file_name = fdata['filename'] + ext
    # file_name = os.path.splitext(product)[0] + '.zip'

    b_download = True
    b_file_okay = False
    complete = False

    full_file_path = os.path.join(CONFIG['GENERAL']['DATA_DIR'], file_name)

    #
    # Establish authentication depending on the mission (S1/S2/S3)
    #
    # Connection.authenticate(satellite)

    #
    # Check if file already exists in location:
    #
    if os.path.exists(full_file_path) and os.path.isfile(full_file_path):

        if not CONFIG['GENERAL']['CHECK_EXISTING']:
            msg = '{} Skipping existing - MD5 not checked'.format(file_name)
            logging.debug(msg)
            if queue is not None:
                queue.put((file_name, {'desc': 'Skipping {name}'}))
            #     queue.put((file_name, msg))
            b_download = False
        else:
            if queue is not None:
                queue.put((file_name,
                          {'desc': 'Checking {name} ...'}))
            #     queue.put((file_name,
            #                '{} Exists - checking MD5 ...'.format(file_name)))
            local_md5 = checksum.md5(full_file_path)
            remote_md5 = md5(fdata)
            if local_md5 == remote_md5:
                msg = '{} Skipping download (MD5 okay)'.format(file_name)
                logging.debug(msg)
                if queue is not None:
                    queue.put((file_name, {'desc': 'Skipping {name}'}))
                #     queue.put((file_name, msg))
                b_download = False
                b_file_okay = True
            else:
                msg = '{} MD5 wrong: redownloading ...'.format(file_name)
                logging.debug(msg)
                # if queue is not None:
                #     queue.put((file_name, msg))

    # if b_download and CONFIG['GENERAL']['SKIP_EXTRACTED'] and \
    #         index.exists(file_name, where='local'):
    #     msg = '{} Skipping download (index exists)'.format(file_name)
    #     logging.debug(msg)
    #     if queue is not None:
    #         queue.put((file_name, msg))
    #     b_download = False

    # if b_download and CONFIG['GENERAL']['SKIP_UPLOADED'] and \
    #         storage.exists(file_name):
    #     msg = '{} Skipping download (already stored)'.format(file_name)
    #     logging.debug(msg)
    #     if queue is not None:
    #         queue.put((file_name, msg))
    #     b_download = False

    if b_download:
        # if queue is not None:
        #     queue.put((file_name, '{} Downloading ... '.format(file_name)))

        #
        # Retrials in case the MD5 hashsum fails
        #
        for i in range(CONFIG['GENERAL']['TRIALS']):
            try:
                complete = _download(fdata['url'], full_file_path, queue=queue)
            except Exception as e:
                logging.debug('{}: {}'.format(file_name, e))
                complete = False

            #
            # After download, check MD5 hashsum
            #
            if not complete:
                logging.debug('{} Download failed, trial {:d}/{:d}.'.format(
                        file_name, i+1, CONFIG['GENERAL']['TRIALS']))
                if queue is not None:
                    queue.put((file_name, {'desc': 'Retrying {name}'}))
                #     queue.put((file_name,
                #                '{} Retrying (trial {:d}/{:d})'
                #                .format(file_name, i+1,
                #                        CONFIG['GENERAL']['TRIALS'])))
            else:
                # if queue is not None:
                #     queue.put((file_name,
                #                '{} Downloaded - Checking MD5...'
                #                .format(file_name)))
                local_md5 = checksum.md5(full_file_path)
                remote_md5 = md5(fdata)
                if local_md5 != remote_md5:
                    logging.debug(
                        '{} MD5 checksum failed, trial {:d}/{:d}.'.format(
                            file_name, i+1, CONFIG['GENERAL']['TRIALS']))
                    if queue is not None:
                        queue.put((file_name,
                                  {'desc': 'Retrying {name}'}))
                    #     queue.put((file_name,
                    #                '{} Retrying ... (trial {:d}/{:d})'
                    #                .format(file_name, i+1,
                    #                        CONFIG['GENERAL']['TRIALS'])))
                else:
                    logging.debug('{} MD5 okay'.format(file_name))
                    if queue is not None:
                        queue.put((file_name, {'desc': '{name} okay'}))
                    #     queue.put((file_name,
                    #                '{} Downloaded - MD5 okay'
                    #                .format(file_name)))
                    b_file_okay = True
                    break

        if not b_file_okay:
            msg = '{} Download failed.'.format(file_name)
            logging.warning(msg)
            if queue is not None:
                queue.put((file_name, {'desc': '{name} Failed'}))
            #     queue.put((file_name, msg))

    if CONFIG['GENERAL']['DOWNLOAD_PREVIEW']:
        full_preview_path = os.path.join(CONFIG['GENERAL']['DATA_DIR'],
                                         fdata['filename']+'.jpeg')

        #
        # If not yet done, download preview file
        #
        if not os.path.exists(full_preview_path) or \
                not os.path.isfile(full_preview_path):
            if not download(fdata['preview'], full_preview_path, quiet=True):
                logging.info('  Preview not available.')

    #
    # Download done (or failed).
    # Send poison pill to parent process.
    #
    if stopqueue and queue is not None:
        queue.put((file_name, ))

    if b_file_okay:
        #
        # File has been downloaded successfully OR already exists
        # --> Return the file path
        #
        logging.debug('Download successful: {}'.format(full_file_path))
        return full_file_path

    elif b_download and not complete:
        #
        # File download failed --> Return FALSE
        #
        logging.error('Download failed: {}'.format(file_name))
        if queue is not None:
            queue.put((file_name, {'desc': '{name} Failed'}))
        #     queue.put((file_name, 'Download failed: {}'.format(file_name)))
        return False

    else:
        #
        # File download was skipped --> Return FALSE
        #
        return False


def download_many(products):
    """Downloads all requested files in parallel, checking for correct MD5 sums.

    Parameters
    ----------
    file_list : list of dict
        A list of dictionaries for each requested file. Can be obtained from
        `scihub_connect.Query.get_file_list()`
    """
    #
    # Parallel downloads
    #
    counter = 0
    total = len(products)
    q = multiprocessing.Manager().Queue()
    pool = multiprocessing.Pool(processes=CONFIG['GENERAL']['N_DOWNLOADS'])
    fn = partial(download, queue=q)
    result = pool.map_async(fn, products)
    while not result.ready():
        while True:
            try:
                msg = q.get(timeout=0.5)
                # fname, msg = q.get(timeout=0.5)
            except multiprocessing.queues.Empty:
                break
            else:
                # if msg is None:
                if len(msg) == 1:
                    counter += 1
                    tty.set_progress(counter, total)
                else:
                    fname, value = msg
                    tty.update(fname, value)
                    # tty.update(fname, msg)
    result.wait()
    tty.finish_status()
    tty.result('All done!')


def redownload(local_file_list):
    """Redownload a list of corrupt files.

    This method will automatically determine the correct source of each file
    from the file name. It will then attempt to redownload the files.

    Parameters
    ----------
    local_file_list : list of str
        A list of local files to be redownloaded from the server.
    """
    def _get_remote_files(local_files, satellite):
        product_names = [os.path.splitext(os.path.split(fpath)[1])[0]
                         for fpath in local_files]
        chunksize = 10
        remote_file_list = []
        for products in helpers.chunks(product_names, chunksize):
            query_string = '({})'.format(
                    ' OR '.join(['identifier:{}'.format(product)
                                 for product in products])
            )
            try:
                remote_file_list.extend(
                    search({'query': query_string, 'satellite': satellite})
                )
            except Exception as e:
                logging.warning('Skipping downloads: {}'.format(e))
        return remote_file_list

    remote_files = []
    for sat in CONFIG['SATELLITES']:
        files = [f for f in local_file_list
                 if os.path.split(f)[1].startswith(sat)]
        remote_files.extend(_get_remote_files(files, sat))

    logging.info('DOWNLOADING {}'.format(len(remote_files)))
    download_many(remote_files)
