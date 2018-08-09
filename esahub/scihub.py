import os
import aiohttp
import asyncio
import lxml.etree as ET
from datetime import datetime, timedelta
import pytz
import re
from esahub.config import CONFIG
from esahub import utils, geo, checksum, tty
from urllib.parse import urlparse, parse_qs, urlencode
from collections import OrderedDict
import hashlib
import logging
logger = logging.getLogger('esahub')
logger.disabled = True


CHUNK = 64 * 1024
PREFIXES = {
    'os': 'http://a9.com/-/spec/opensearch/1.1/',
    'opensearch': 'http://a9.com/-/spec/opensearch/1.1/',
    'doc': 'http://www.w3.org/2005/Atom',
    'gml': 'http://www.opengis.net/gml'
}
DOWNLOAD_URL_PATTERN = \
    "{host}/odata/v1/Products('{uuid}')/$value"
CHECKSUM_URL_PATTERN = \
    "{host}/odata/v1/Products('{uuid}')/Checksum/Value/$value"
PREVIEW_URL_PATTERN = \
    "{host}/odata/v1/Products('{uuid}')/Products('Quicklook')/$value"
DATETIME_FMT = '%Y-%m-%dT%H:%M:%S.000Z'


# -----------------------------------------------------------------------------
# HTTP CONNECTION METHODS
# This is all the async stuff
# -----------------------------------------------------------------------------
class NotFoundError(Exception):
    pass


class SessionManager():
    _sessions = {}

    def __init__(self):
        pass

    def __getitem__(self, server):
        if server not in self._sessions:
            cfg = CONFIG['SERVERS'][server]
            auth = aiohttp.BasicAuth(login=cfg['user'],
                                     password=cfg['password'])
            connector = aiohttp.TCPConnector(limit=2)
            self._sessions[server] = aiohttp.ClientSession(
                auth=auth, connector=connector)
        return self._sessions[server]

    def __del__(self):
        loop = asyncio.get_event_loop()
        closer_tasks = []
        for server, session in self._sessions.items():
            closer_tasks.append(
                session.close()
            )
        loop.run_until_complete(asyncio.wait(closer_tasks))


session = SessionManager()


def block(fn, *args, **kwargs):
    """Run an async function and block."""
    task = fn(*args, **kwargs)
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(task)
    return result


def get_response(url):
    async def _resp(url):
        server = _get_server_from_url(url)
        async with session[server].get(url) as resp:
            return resp
    return block(_resp, url)


def resolve(url, server=None):
    return block(_resolve, url, server=server)


async def _resolve(url, server=None):
    if server is None:
        server = _get_server_from_url(url)

    async with session[server].get(url) as response:
        return await response.text()


async def get_total_results(url):
    response = await _resolve(url)
    xml = response.encode('utf-8')
    root = ET.fromstring(xml)
    try:
        total_results = int(root.find('os:totalResults', PREFIXES).text)
    except TypeError:
        total_results = 0
    except AttributeError as e:
        raise AttributeError("Could not extract total results from URL "
                             "{}: {}".format(url, e))
    return total_results


async def _ping_single(server):
    cfg = CONFIG['SERVERS'][server]
    url = '{host}/search?q=*:*'.format(host=cfg['host'])
    async with session[server].get(url) as response:
        return (server, response.status)


async def _download(url, destination, pbar=None, return_md5=False):
    """Downloads a file from the remote server into the specified destination.

    Parameters
    ----------
    url : str
        The source URL.
    destination : str
        The local target file path.
    pbar : tqdm progress bar, optional
        Update progress bar.

    Returns
    -------
    bool
        True if successful, False otherwise.
    """
    #
    # Create directory.
    #
    path, file_name = os.path.split(destination)
    os.makedirs(path, exist_ok=True)

    if return_md5:
        hash_md5 = hashlib.md5()

    server = _get_server_from_url(url)
    async with session[server].get(url) as response:
        size = int(response.headers['Content-Length'])
        if pbar is not None:
            pbar.n = 0
            pbar.total = size
            pbar.refresh()
        chunks_done = 0
        with open(destination, 'wb') as f:
            async for data in response.content.iter_chunked(CHUNK):
                if return_md5:
                    hash_md5.update(data)
                f.write(data)
                chunks_done += 1
                progress = len(data)
                tty.screen.status(progress=progress)
                if pbar is not None:
                    # pbar.update(CHUNK)
                    pbar.update(len(data))

    # if pbar is not None:
    #     pbar.close()

    if return_md5:
        return (True, hash_md5.hexdigest().lower())
    else:
        return True


# -----------------------------------------------------------------------------
# XML PARSING
# -----------------------------------------------------------------------------
def parse_page(xml):
    file_list = []

    try:
        root = ET.fromstring(xml)
        # try:
        #     total_results = int(root.find('os:totalResults', PREFIXES).text)
        # except TypeError:
        #     total_results = 0

        for entry in root.findall('doc:entry', PREFIXES):

            filename = entry.find("./doc:str[@name='identifier']",
                                  PREFIXES).text
            ingestiondate = utils.to_date(
                entry.find("./doc:date[@name='ingestiondate']", PREFIXES).text,
                output='date')
            try:
                footprint_tag = entry.find("./doc:str[@name='gmlfootprint']",
                                           PREFIXES).text
                match = re.search('<gml:coordinates>(.*)</gml:coordinates>',
                                  footprint_tag)
                coords = geo.gml_to_polygon(match.groups()[0])
            except AttributeError:
                coords = None

            filesize = utils.h2b(entry.find("./doc:str[@name='size']",
                                            PREFIXES).text)
            preview_url = entry.find("./doc:link[@rel='icon']",
                                     PREFIXES).attrib['href']
            try:
                rel_orbit = int(entry.find(
                    "doc:int[@name='relativeorbitnumber']", PREFIXES).text)
            except AttributeError:
                rel_orbit = None

            try:
                orbit_dir = entry.find("doc:str[@name='orbitdirection']",
                                       PREFIXES).text.upper()
            except AttributeError:
                orbit_dir = None

            file_dict = {
                'title': entry.find('doc:title', PREFIXES).text,
                'url': entry.find('doc:link', PREFIXES).attrib['href'],
                'preview': preview_url,
                'uuid': entry.find('doc:id', PREFIXES).text,
                'filename': filename,
                'size': filesize,
                'ingestiondate': ingestiondate,
                'coords': coords,
                'orbit_direction': orbit_dir,
                'rel_orbit': rel_orbit
            }
            file_dict['host'] = _get_host_from_url(file_dict['url'])
            file_list.append(file_dict)

    except ET.XMLSyntaxError:
        # not valid XML
        file_list = []

    return file_list


async def _files_from_url(url):
    xml = await _resolve(url)
    result = parse_page(xml.encode('utf-8'))
    tty.screen.status(progress=len(result))
    return result


async def _get_file_list_from_url(url, limit=None):
    # Parse first page to get total number of results.
    total_results = await get_total_results(url)
    host = urlparse(url).netloc
    tty.screen.status(desc='Querying {host}'.format(host=host),
                      total=total_results, mode='bar')

    if limit is None:
        total = total_results
    else:
        total = min(limit, total_results)

    urls = [url] + [u for u in _generate_next_url(url, total=total)]

    tasks = [_files_from_url(u) for u in urls]
    results = await asyncio.gather(*tasks)
    result = utils.flatten(results)

    return result


# -----------------------------------------------------------------------------
# QUERY BUILDING
# -----------------------------------------------------------------------------
def _parse_time_parameter(value):
    # Default ingestiontime query parameters
    start = '1970-01-01T00:00:00.000Z'
    end = 'NOW'
    DATE_FMT = '%Y-%m-%dT00:00:00.000Z'

    if value == 'today':
        start = datetime.strftime(datetime.now(pytz.utc), DATE_FMT)

    elif value == 'yesterday':
        start = datetime.strftime(datetime.now(pytz.utc)
                                  - timedelta(1), DATE_FMT)
        end = datetime.strftime(datetime.now(pytz.utc), DATE_FMT)

    elif value == 'midnight':
        end = datetime.strftime(datetime.now(pytz.utc), DATE_FMT)

    elif value == '24h':
        start = datetime.strftime(datetime.now(pytz.utc)
                                  - timedelta(1), DATETIME_FMT)
        end = datetime.strftime(datetime.now(pytz.utc), DATETIME_FMT)

    else:
        parsed = utils.parse_datetime(value)
        if not isinstance(parsed, tuple):
            start = datetime.strftime(parsed, DATETIME_FMT)
            end = start
        else:
            if parsed[0] is not None:
                start = datetime.strftime(parsed[0], DATETIME_FMT)
            if parsed[1] is not None:
                end = datetime.strftime(parsed[1], DATETIME_FMT)

    return start, end


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

        elif key == 'time':
            start, end = _parse_time_parameter(val)

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
                    logger.error(
                        '{0} {1}'.format(tty.error('Location not found:'), loc)
                    )

        elif key == 'type':
            query_list.append('producttype:{}'.format(query['type']))

        elif key == 'orbit':
            if val.upper() in ['ASC', 'ASCENDING']:
                orbit = 'ASCENDING'
            elif val.upper() in ['DESC', 'DESCENDING']:
                orbit = 'DESCENDING'
            else:
                raise ValueError("Invalid value for `orbit`: '{}'"
                                 .format(val))
            query_list.append('orbitdirection:{}'.format(orbit))

        elif key == 'id':
            query_list.append('identifier:{}'.format(query['id']))

        elif key == 'query':
            query_list.append('{}'.format(query['query']))

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


# -----------------------------------------------------------------------------
# UTILITY FUNCTIONS
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

    if total is not None:
        last_start = total - q_params['rows']
        q_params['rows'] = min(q_params['rows'], total)

    while total is None or q_params['start'] < last_start:
        q_params['start'] += q_params['rows']
        parsed_url = parsed_url._replace(query=urlencode(q_params, doseq=True))
        yield parsed_url.geturl()


def _get_available_servers():
    servers = [server for server, conf in CONFIG['SERVERS'].items()
               if len(conf['user']) > 0 and len(conf['password']) > 0]
    return servers


def _get_server_from_url(url):
    if 'server' in CONFIG['GENERAL']['QUERY']:
        return CONFIG['GENERAL']['QUERY']['server']
    for servername, cfg in CONFIG['SERVERS'].items():
        if cfg['host'] in url:
            return servername

    raise Exception("Could not determine server for {url}!".format(url=url))


def _get_host_from_url(url):
    p = urlparse(url)
    host = '{}://{}/{}'.format(
        p.scheme, p.netloc, p.path.strip('/').split('/')[0])
    return host


def _auto_detect_server_from_query(query, available_only=False):
    servers = None

    if 'satellite' in query and query['satellite'] in CONFIG['SATELLITES']:
        servers = CONFIG['SATELLITES'][query['satellite']]['source']

    if 'identifier' in query:
        sat = query['identifier'][:3]
        if sat in CONFIG['SATELLITES']:
            servers = CONFIG['SATELLITES'][sat]['source']

    if 'mission' in query:
        sats = utils.select(CONFIG['SATELLITES'], platform=query['mission'])
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


async def _uuid_from_identifier(identifier):
    identifier = os.path.splitext(os.path.split(identifier)[1])[0]
    results = await _search({'identifier': identifier+'*'})
    if len(results) == 0:
        raise NotFoundError('Product not found: {}'.format(identifier))
    return results[0]['uuid']


async def _host_and_uuid_from_identifier(identifier):
    identifier = os.path.splitext(os.path.split(identifier)[1])[0]
    results = await _search({'identifier': identifier+'*'})
    if len(results) == 0:
        raise NotFoundError('Product not found: {}'.format(identifier))
    return (results[0]['host'], results[0]['uuid'])


def _host_from_uuid(uuid):
    #
    # IMPLEMENT THIS
    #
    return None


async def _download_url_from_identifier(identifier):
    host, uuid = await _host_and_uuid_from_identifier(identifier)
    return _download_url_from_uuid(uuid, host=host)


async def _checksum_url_from_identifier(identifier):
    host, uuid = await _host_and_uuid_from_identifier(identifier)
    return _checksum_url_from_uuid(uuid, host=host)


async def _preview_url_from_identifier(identifier):
    host, uuid = await _host_and_uuid_from_identifier(identifier)
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
# PUBLIC API METHODS
# -----------------------------------------------------------------------------
# def ping(server=None):
#     results = {}
#     if server is not None:
#         servers = [server]
#     else:
#         servers = list(CONFIG['SERVERS'].keys())

#     pool = multiprocessing.Pool(processes=len(servers))
#     results = pool.map_async(_ping_single, servers)
#     # pool.close()
#     # pool.join()
#     # for servername,server in servers.items():
#     while not results.ready():
#         time.sleep(1)
#     return results.get()

def search(*args, **kwargs):
    return block(_search, *args, **kwargs)


async def _search(query={}, server='auto', limit=None, **kwargs):
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
    query_string = _build_query(query)

    tasks = []
    for servername in servers:
        server = CONFIG['SERVERS'][servername]
        url = '{url}/search?{q}'.format(
            url=server['host'], q=query_string
        )
        logger.debug('Trying server {}: {}'.format(servername, url))
        tasks.append(
            _get_file_list_from_url(url, limit=limit)
        )
    results = await asyncio.gather(*tasks)
    results = utils.flatten(results)

    #
    # Delete duplicate results (if product is on multiple servers).
    # TODO: This should be done in the order of preference as
    # given by CONFIG['SERVERS'] !
    #
    unique = utils.unique_by(results, lambda x: x['filename'])
    if limit is not None:
        unique = unique[:limit]

    return unique


async def _md5(product=None, uuid=None):
    if product is not None:
        if type(product) is dict and 'uuid' in product and 'host' in product:
            md5_url = _checksum_url_from_uuid(product['uuid'],
                                              host=product['host'])
        elif type(product) is str:
            md5_url = await _checksum_url_from_identifier(product)
        else:
            return False

    elif uuid is not None:
        md5_url = _checksum_url_from_uuid(uuid)

    server = _get_server_from_url(md5_url)
    async with session[server].get(md5_url) as response:
        result = await response.read()
    return result.decode().lower()

    # if PY2:
    #     return result.lower()
    # else:
    #     return result.decode().lower()


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
    return block(_md5, product=product, uuid=uuid)


def exists(product):
    search_results = search({'identifier': product+'*'}, limit=1)
    return len(search_results) > 0


def download(product):
    if isinstance(product, list):
        # Multiple downloads
        # tty.screen.status(total=len(product))
        tasks = [_single_download(p, return_md5=True) for p in product]
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(asyncio.gather(*tasks))
    else:
        # Single download
        result = block(_single_download, product=product)

    return result


async def _single_download(product, return_md5=False):
    """Download a satellite product.

    Checks for file existence and MD5 checksum.

    Parameters
    ----------
    product : str or dict
        The name of the product to be downloaded from SciHub.
        Alternatively, a dictionary representing a search result from SciHub.
    return_md5 : bool, optional
        Whether to compute and return the md5 hash sum (default: False).

    Returns
    -------
    str
        The local file path if the download was successful OR the file already
        exists and passes the md5 checksum test. False otherwise.
    """
    if type(product) is dict:
        fdata = product
    else:
        fdata = await _search(
            {'identifier': os.path.splitext(product)[0]+'*'}
        )
        fdata = fdata[0]

    satellite = utils.get_satellite(fdata['filename'])
    ext = CONFIG['SATELLITES'][satellite]['ext']
    file_name = fdata['filename'] + ext

    pbar_key = file_name
    pbar = tty.screen[pbar_key]

    b_download = True
    b_file_okay = False
    complete = False

    full_file_path = os.path.join(CONFIG['GENERAL']['DATA_DIR'], file_name)

    #
    # Check if file already exists in location:
    #
    if os.path.exists(full_file_path) and os.path.isfile(full_file_path):

        if not CONFIG['GENERAL']['CHECK_EXISTING']:
            #
            # File exists and won't be checked.
            #
            msg = '{} Skipping existing - MD5 not checked'.format(file_name)
            tty.screen[pbar_key] = 'Skipping {name}'
            logger.debug(msg)
            b_download = False

        else:
            #
            # File exists and will be checked for md5 consistency
            #
            local_md5 = checksum.md5(full_file_path)
            remote_md5 = await _md5(fdata)
            if local_md5 == remote_md5:
                msg = '{} Skipping download (MD5 okay)'.format(file_name)
                tty.screen[pbar_key] = 'Skipping {name} (okay)'
                logger.debug(msg)
                b_download = False
                b_file_okay = True
            else:
                msg = '{} MD5 wrong: redownloading ...'.format(file_name)
                tty.screen[pbar_key] = 'Redownloading {name}'
                logger.debug(msg)

    if b_download:
        #
        # Retrials in case the MD5 hashsum fails
        #
        for i in range(CONFIG['GENERAL']['TRIALS']):
            complete = await _download(fdata['url'], full_file_path,
                                       pbar=pbar, return_md5=return_md5)
            if return_md5:
                complete, local_md5 = complete

            #
            # After download, check MD5 hashsum
            #
            if not complete:
                #
                # Download incomplete.
                #
                msg = '{} Download failed, trial {:d}/{:d}.'.format(
                        file_name, i+1, CONFIG['GENERAL']['TRIALS'])
                logger.debug(msg)
                tty.screen[pbar_key] = 'Failed: {name}'
            else:
                #
                # Download completed.
                #
                if not return_md5:
                    local_md5 = checksum.md5(full_file_path)

                remote_md5 = await _md5(fdata)
                if local_md5 != remote_md5:
                    #
                    # Download failed.
                    #
                    msg = '{} MD5 checksum failed, trial {:d}/{:d}.'.format(
                            file_name, i+1, CONFIG['GENERAL']['TRIALS'])
                    logger.debug(msg)
                    tty.screen[pbar_key] = 'Failed: {name}'
                else:
                    #
                    # Download completed and successful.
                    #
                    msg = '{} MD5 okay'.format(file_name)
                    logger.debug(msg)
                    tty.screen[pbar_key] = 'MD5 okay: {name}'
                    b_file_okay = True
                    break

        if not b_file_okay:
            msg = '{} Download failed.'.format(file_name)
            logger.warning(msg)
            tty.screen[pbar_key] = 'Failed: {name}'

    if CONFIG['GENERAL']['DOWNLOAD_PREVIEW']:
        full_preview_path = os.path.join(CONFIG['GENERAL']['DATA_DIR'],
                                         fdata['filename']+'.jpeg')
        #
        # If not yet done, download preview file
        #
        if not os.path.exists(full_preview_path) or \
                not os.path.isfile(full_preview_path):
            if not _download(fdata['preview'], full_preview_path):
                logger.info('  Preview not available.')

    if b_file_okay:
        #
        # File has been downloaded successfully OR already exists
        # --> Return the file path
        #
        msg = 'Download successful: {}'.format(full_file_path)
        logger.debug(msg)
        tty.screen[pbar_key] = 'Successful: {name}'
        if return_md5:
            return full_file_path, local_md5
        else:
            return full_file_path

    elif b_download and not complete:
        #
        # File download failed --> Return FALSE
        #
        msg = 'Download failed: {}'.format(file_name)
        logger.error(msg)
        tty.screen[pbar_key] = 'Failed: {name}'
        return False

    else:
        #
        # File download was skipped --> Return FALSE
        #
        return False


async def _get_remote_files_per_satellite(files, satellite):
        product_names = [os.path.splitext(os.path.split(fpath)[1])[0]
                         for fpath in files]
        chunksize = 10
        queries = []
        for products in utils.chunks(product_names, chunksize):
            query_string = '({})'.format(
                    ' OR '.join(['identifier:{}'.format(product)
                                 for product in products])
            )
            queries.append({'query': query_string, 'satellite': satellite})
        tasks = [_search(q) for q in queries]
        result = await asyncio.gather(*tasks)
        return utils.flatten(result)


def _get_remote_files(files):
    tasks = []
    for sat in CONFIG['SATELLITES']:
        sat_files = [f for f in files
                     if os.path.split(f)[1].startswith(sat)]
        tasks.append(_get_remote_files_per_satellite(sat_files, sat))
    loop = asyncio.get_event_loop()
    results = loop.run_until_complete(asyncio.gather(*tasks))
    return utils.flatten(results)


def redownload(local_file_list):
    """Redownload a list of corrupt files.

    This method will automatically determine the correct source of each file
    from the file name. It will then attempt to redownload the files.

    Parameters
    ----------
    local_file_list : list of str
        A list of local files to be redownloaded from the server.
    """
    remote_files = _get_remote_files(local_file_list)
    logger.info('DOWNLOADING {}'.format(len(remote_files)))
    download(remote_files)
