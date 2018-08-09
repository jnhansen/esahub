from esahub import scihub, utils, checksum, check, main
import unittest
import contextlib
import logging
import re
import datetime as DT
import pytz
import os
import sys
import subprocess
from shapely.wkt import loads as wkt_loads
from esahub.tests import config as test_config
from esahub import config

logger = logging.getLogger('esahub')

PY2 = sys.version_info < (3, 0)
SMALL_SIZE_QUERY = 'size: ???.* KB'

if hasattr(unittest.TestCase, 'subTest'):
    class TestCase(unittest.TestCase):
        pass
else:
    class TestCase(unittest.TestCase):
        @contextlib.contextmanager
        def subTest(self, msg='', **params):
            """Mock subTest method so no exception is raised under Python2."""
            utils.eprint('subTest:', msg, params)
            yield
            return


# -----------------------------------------------------------------------------
# TEST SETUP
# -----------------------------------------------------------------------------
def setUpModule():
    test_config.set_test_config()
    test_config.prepare()


def tearDownModule():
    test_config.cleanup()


# -----------------------------------------------------------------------------
# SCIHUB
# -----------------------------------------------------------------------------
class ScihubTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        test_config.set_test_config()

    # def setUp(self):

    def test_servers(self):
        for name in scihub._get_available_servers():
            cfg = config.CONFIG['SERVERS'][name]
            with self.subTest(server_name=name):
                url = '{}/search?q=*:*'.format(cfg['host'])
                response = scihub.get_response(url)
                #
                # Assert that the HTML response has status code 200 (OK)
                #
                self.assertEqual(response.status, 200)

    def test__generate_next_url(self):
        # _generate_next_url(url, total=None)
        pass

    def test__parse_page(self):
        # _parse_page(url, first=False)
        pass

    def test__get_file_list_from_url(self):
        # _get_file_list_from_url(url, limit=None)
        pass

    def test__callback(self):
        # _callback(result)
        pass

    def test__build_query(self):
        # _build_query(query={})
        pass

    def test__build_url(self):
        # _build_url(query, server)
        pass

    def test__download(self):
        # _download(url, destination, quiet=None, queue=None)
        pass

    def test__get_file_list_wrapper(self):
        # _get_file_list_wrapper(url)
        pass

    def test__ping_single(self):
        # _ping_single(servername)
        pass

    def test__auto_detect_server_from_query(self):
        queries = [
            # (query, server)
            ({'mission': 'Sentinel-1'},
             config.CONFIG['SATELLITES']['S1A']['source']),
            ({'mission': 'Sentinel-2'},
             config.CONFIG['SATELLITES']['S2A']['source']),
            ({'mission': 'Sentinel-3'},
             config.CONFIG['SATELLITES']['S3A']['source']),
            ({'satellite': 'S1A'},
             config.CONFIG['SATELLITES']['S1A']['source']),
            ({'satellite': 'S3A'},
             config.CONFIG['SATELLITES']['S3A']['source']),
            ({'satellite': 'S2B'},
             config.CONFIG['SATELLITES']['S2B']['source']),
            ({'identifier': "S1A_IW_OCN__2SDV_20160924T181320_"
                            "20160924T181345_013198_014FDF_6692.zip"},
             config.CONFIG['SATELLITES']['S1A']['source'])
        ]
        for query, server in queries:
            with self.subTest(query=query):
                self.assertEqual(
                    scihub._auto_detect_server_from_query(query), server
                )

    def test__uuid_from_identifier(self):
        products = scihub.search({}, limit=1)
        for product in products:
            with self.subTest(product=product):
                self.assertEqual(
                    scihub.block(scihub._uuid_from_identifier,
                                 product['title']),
                    product['uuid']
                )

    # def test__download_url_from_identifier(self):
    #     # _download_url_from_identifier(identifier)
    #     pass
    # def test__checksum_url_from_identifier(self):
    #     # _checksum_url_from_identifier(identifier)
    #     pass
    # def test__preview_url_from_identifier(self):
    #     # _preview_url_from_identifier(identifier)
    #     pass
    # def test__download_url_from_uuid(self):
    #     # _download_url_from_uuid(uuid, host=None)
    #     pass
    # def test__checksum_url_from_uuid(self):
    #     # _checksum_url_from_uuid(uuid, host=None)
    #     pass
    # def test__preview_url_from_uuid(self):
    #     # _preview_url_from_uuid(uuid, host=None)
    #     pass

    def test_get_response(self):
        for name in scihub._get_available_servers():
            with self.subTest(server_name=name):
                response = scihub.get_response(
                    scihub._build_url({'query': '*:*'}, name)
                )
                self.assertEqual(response.status, 200)

    def test_md5_from_file(self):
        for f in utils.ls(config.CONFIG['GENERAL']['DATA_DIR']):
            with self.subTest(file=f):
                #
                # Assert that the md5 sum computed from the local file is equal
                # to the md5 sum obtained from the remote server.
                #
                try:
                    remote_md5 = scihub.md5(f)
                    self.assertEqual(
                        checksum.md5(f), remote_md5
                    )
                except Exception as e:
                    self.fail('Remote MD5 could not be obtained: {}'.format(e))

    def test_exists_true(self):
        existing = scihub.search({}, limit=1)
        for e in existing:
            with self.subTest(product=e['filename']):
                self.assertTrue(scihub.exists(e['filename']))

    def test_exists_false(self):
        not_existing = 'this_is_not_on_scihub'
        self.assertFalse(scihub.exists(not_existing))


# -----------------------------------------------------------------------------
# SCIHUB SEARCH
# -----------------------------------------------------------------------------
class ScihubSearchTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        test_config.set_test_config()

    def test_query_entries(self):
        query = {'mission': 'Sentinel-3'}
        server = scihub._auto_detect_server_from_query(query,
                                                       available_only=True)[0]
        url = scihub._build_url(query, server)
        html = scihub.resolve(url)
        #
        # Assert that the number of entries found on the page matches the
        # number of entries requested per page.
        #
        self.assertEqual(html.count('<entry>'),
                         config.CONFIG['GENERAL']['ENTRIES'])

    def test_orbit_query(self):
        for search_str, orbit in [
            ('ASC', 'ASCENDING'),
            ('DESC', 'DESCENDING')
        ]:
            query = {'orbit': search_str}
            result = scihub.search(query, limit=20)
            for prod in result:
                self.assertEqual(prod['orbit_direction'], orbit)

    def test_id_query(self):
        prod = scihub.search({}, limit=5)[-1]
        query = {'id': prod['title']}
        result = scihub.search(query)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], prod)

    def test_queries(self):
        queries = [
            # (name, query)
            ('S3', {'mission': 'Sentinel-3'}),
        ]
        for name, q in queries:
            with self.subTest(name=name):
                server = scihub._auto_detect_server_from_query(
                    q, available_only=True)[0]
                url = scihub._build_url(q, server=server)
                response = scihub.get_response(url)
                #
                # Assert that queries for each mission return a
                # status code 200 (OK)
                #
                self.assertEqual(response.status, 200)

        with self.subTest('count entries'):
            q = {'mission': 'Sentinel-3'}
            server = scihub._auto_detect_server_from_query(
                q, available_only=True)[0]
            url = scihub._build_url(q, server=server)
            html = scihub.resolve(url)
            #
            # Assert that the number of entries found on the page matches the
            # number of entries requested per page.
            #
            self.assertEqual(html.count('<entry>'),
                             config.CONFIG['GENERAL']['ENTRIES'])

    def test_temporal_queries(self):
        with self.subTest('yesterday'):
            file_list = scihub.search({'mission': 'Sentinel-3',
                                       'time': 'yesterday'},
                                      limit=200)
            yesterday = DT.datetime.now(pytz.utc)-DT.timedelta(1)
            today = DT.datetime.now(pytz.utc)
            start = DT.datetime(yesterday.year, yesterday.month, yesterday.day,
                                tzinfo=pytz.utc)
            end = DT.datetime(today.year, today.month, today.day,
                              tzinfo=pytz.utc)
            for f in file_list:
                #
                # Assert that the ingestiondate of each entry was yesterday.
                #
                self.assertGreaterEqual(f['ingestiondate'], start)
                self.assertLessEqual(f['ingestiondate'], end)

        with self.subTest('today'):
            file_list = scihub.search({'mission': 'Sentinel-3',
                                       'time': 'today'},
                                      limit=200)
            today = DT.datetime.now(pytz.utc)
            start = DT.datetime(today.year, today.month, today.day,
                                tzinfo=pytz.utc)
            for f in file_list:
                #
                # Assert that the ingestiondate of each entry is today.
                #
                self.assertGreaterEqual(f['ingestiondate'], start)

    #
    # NOTE: This test presently fails because apparantly,
    # SciHub's `intersects` parameter does not work reliably.
    #
    def test_spatial_queries(self):
        loc, ref_coords = next(iter(config.CONFIG['LOCATIONS'].items()))
        with self.subTest(location=loc):
            file_list = scihub.search(
                {'location': [loc], 'time': 'to 2017-09-01T00:00:00Z'},
                server='S3', limit=20)
            for f in file_list:
                with self.subTest(product=f['filename']):
                    #
                    # Assert that the products indeed intersect the
                    # requested location.
                    #
                    distance = wkt_loads(f['coords']).distance(
                        wkt_loads(ref_coords))
                    utils.eprint('Distance: {}'.format(distance))
                    self.assertLessEqual(distance, 0.3)

    def test_get_file_list(self):
        q = {'mission': 'Sentinel-3'}
        limit = 107
        file_list = scihub.search(q, limit=limit)
        #
        # Assert that only `limit` entries are returned.
        #
        self.assertEqual(limit, len(file_list))
        for f in file_list:
            #
            # Assert that each entry contains the attributes `url`, `uuid` and
            # `filename`.
            #
            self.assertIn('url', f)
            self.assertIn('uuid', f)
            self.assertIn('filename', f)


# -----------------------------------------------------------------------------
# SCIHUB DOWNLOAD
# -----------------------------------------------------------------------------
class ScihubDownloadTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        test_config.set_test_config()

    def setUp(self):
        test_config.clear_test_data()

    def tearDown(self):
        test_config.clear_test_data()

    def test_download(self):
        file_list = scihub.search({'query': SMALL_SIZE_QUERY}, limit=1)
        for f in file_list:
            with self.subTest(url=f['url']):
                result = scihub.download(f)
                #
                # Assert that the download didn't fail and that
                # the returned file path exists.
                #
                self.assertNotEqual(result, False)
                self.assertTrue(os.path.isfile(result))

    def test_download_many(self):
        file_list = scihub.search({'query': SMALL_SIZE_QUERY},
                                  limit=2)
        scihub.download(file_list)
        #
        # Assert that all downloads were successful.
        #
        local_files = utils.ls(config.CONFIG['GENERAL']['DATA_DIR'])
        local_files_identifiers = [os.path.splitext(os.path.split(_)[1])[0]
                                   for _ in local_files]
        for f in file_list:
            self.assertIn(f['filename'], local_files_identifiers)
        for f in local_files:
            with self.subTest(file=f):
                _, healthy, msg = check.check_file(f, mode='file')
                utils.eprint(msg)
                self.assertTrue(healthy)

    def test_redownload(self):
        test_config.copy_corrupt_data()
        local_files = utils.ls(config.CONFIG['GENERAL']['DATA_DIR'])
        scihub.redownload(local_files)
        new_local_files = utils.ls(config.CONFIG['GENERAL']['DATA_DIR'])
        self.assertEqual(set(local_files), set(new_local_files))
        for f in local_files:
            with self.subTest(file=f):
                _, healthy, msg = check.check_file(f, mode='file')
                utils.eprint(msg)
                self.assertTrue(healthy)


# -----------------------------------------------------------------------------
# CHECK
# -----------------------------------------------------------------------------
class CheckTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        test_config.set_test_config()

    def setUp(self):
        test_config.copy_test_data()

    def tearDown(self):
        test_config.clear_test_data()

    def test_check_file_md5_healthy(self):
        for f in utils.ls(config.CONFIG['GENERAL']['DATA_DIR']):
            with self.subTest(file=f):
                #
                # Assert that the files check out in `md5` mode.
                #
                try:
                    file_path, healthy, message = \
                        check.check_file(f, mode='md5')
                    self.assertTrue(healthy)
                except Exception as e:
                    self.fail('File check failed: {}'.format(e))

    def test_check_file_zip_healthy(self):
        for f in utils.ls(config.CONFIG['GENERAL']['DATA_DIR']):
            with self.subTest(file=f):
                #
                # Assert that the files check out in `file` mode.
                #
                try:
                    file_path, healthy, message = \
                        check.check_file(f, mode='file')
                    self.assertTrue(healthy)
                except Exception as e:
                    self.fail('File check failed: {}'.format(e))

    def test_check_file_md5_corrupt(self):
        test_config.clear_test_data()
        test_config.copy_corrupt_data()
        for f in utils.ls(config.CONFIG['GENERAL']['DATA_DIR']):
            with self.subTest(file=f):
                #
                # Assert that the files are detected as corrupt in `md5` mode.
                #
                try:
                    file_path, healthy, message = \
                        check.check_file(f, mode='md5')
                    self.assertFalse(healthy)
                except Exception as e:
                    self.fail('File check failed: {}'.format(e))

    def test_check_file_zip_corrupt(self):
        test_config.clear_test_data()
        test_config.copy_corrupt_data()
        for f in utils.ls(config.CONFIG['GENERAL']['DATA_DIR']):
            with self.subTest(file=f):
                #
                # Assert that the files are detected as corrupt in `file` mode.
                #
                try:
                    file_path, healthy, message = \
                        check.check_file(f, mode='file')
                    self.assertFalse(healthy)
                except Exception as e:
                    self.fail('File check failed: {}'.format(e))


# -----------------------------------------------------------------------------
# CHECKSUM
# -----------------------------------------------------------------------------
class ChecksumTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        test_config.set_test_config()

    def setUp(self):
        test_config.copy_test_data()

    def tearDown(self):
        test_config.clear_test_data()

    def test_md5(self):
        for f in utils.ls(config.CONFIG['GENERAL']['DATA_DIR']):
            with self.subTest(file=f):
                #
                # Assert that the md5 checksum returned by checksum.md5() is
                # equal to the md5 sum returned by bash md5 or md5sum tool.
                #
                for exe in ['md5', 'md5sum']:
                    if utils._which(exe) is not None:
                        bash_output = subprocess.check_output([exe, f])
                        if not PY2:
                            bash_output = bash_output.decode()
                        bash_md5 = re.search('[a-zA-Z0-9]{32}',
                                             bash_output).group()
                        break
                self.assertEqual(
                    checksum.md5(f), bash_md5
                )

    def test_etag_small_files(self):
        for f in utils.ls(config.CONFIG['GENERAL']['DATA_DIR']):
            with self.subTest(file=f):
                #
                # Assert that the computed etag is equal to the md5
                # checksum for files smaller than the chunksize.
                #
                size_mb = max(10, int(os.path.getsize(f) / 1024**2))
                self.assertEqual(
                    checksum.md5(f), checksum.etag(f, chunksize=2 * size_mb)
                )

    # def test_etag_large_files(self):
    #     pass


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
class MainTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        test_config.set_test_config()
        cls.check_mode = config.CONFIG['GENERAL']['CHECK_MODE']
        config.CONFIG['GENERAL']['CHECK_MODE'] = 'file'

    @classmethod
    def tearDownClass(cls):
        config.CONFIG['GENERAL']['CHECK_MODE'] = cls.check_mode

    def setUp(self):
        test_config.copy_test_data()

    def tearDown(self):
        test_config.clear_all()

    def test_ls(self):
        q = {'time': 'today', 'satellite': 'S3A',
             'location': ['Ireland_Mace_Head']}
        files = scihub.search(q)
        result = main.ls(q)
        self.assertEqual(len(result), len(files))

    def test_get(self):
        test_config.clear_test_data()
        q = {'satellite': 'S3A', 'query': SMALL_SIZE_QUERY}
        files = scihub.search(q, limit=2)
        main.get(q, limit=2)

        for f in files:
            ext = '.zip'
            with self.subTest(product=f['filename']):
                self.assertTrue(
                    os.path.isfile(os.path.join(
                        config.CONFIG['GENERAL']['DATA_DIR'],
                        f['filename']) + ext)
                )

    def test_doctor(self):
        test_config.copy_corrupt_data()
        corrupt_files = utils.ls(test_config.TEST_DATA_DIR_CORRUPT,
                                 path=False)
        # healthy_files = utils.ls(test_config.TEST_DATA_DIR_ORIGINAL,
        #                          path=False)
        result = main.doctor()
        bad_files = [os.path.split(status[0])[1]
                     for status in result if status[1] is False]

        #
        # Assert that the number of healthy/corrupt files detected are correct
        #
        self.assertEqual(len(bad_files), len(corrupt_files))
        for corrupt_file in corrupt_files:
            #
            # Assert that each corrupt file has been registered.
            #
            self.assertIn(corrupt_file, bad_files)

    def test_doctor_delete(self):
        test_config.copy_corrupt_data()
        corrupt_files = utils.ls(test_config.TEST_DATA_DIR_CORRUPT,
                                 path=False)
        healthy_files = utils.ls(test_config.TEST_DATA_DIR_ORIGINAL,
                                 path=False)
        main.doctor(delete=True)
        #
        # Assert that the corrupt files have been deleted.
        #
        for f in corrupt_files:
            self.assertFalse(os.path.isfile(os.path.join(
                    config.CONFIG['GENERAL']['DATA_DIR'], f)))

        #
        # Assert that the healthy files have not been deleted.
        #
        for f in healthy_files:
            self.assertTrue(os.path.isfile(os.path.join(
                    config.CONFIG['GENERAL']['DATA_DIR'], f)))

    def test_doctor_repair(self):
        test_config.copy_corrupt_data()
        corrupt_files = utils.ls(test_config.TEST_DATA_DIR_CORRUPT,
                                 path=False)
        # healthy_files = utils.ls(test_config.TEST_DATA_DIR_ORIGINAL,
        #                            path=False)
        main.doctor(repair=True)

        for f in corrupt_files:
            repaired_f = os.path.join(config.CONFIG['GENERAL']['DATA_DIR'], f)
            with self.subTest(file=repaired_f):
                #
                # Assert that each corrupt file has been repaired.
                #
                _, healthy, msg = check.check_file(repaired_f, mode='file')
                utils.eprint(msg)
                self.assertTrue(healthy)


# -----------------------------------------------------------------------------
# utils
# -----------------------------------------------------------------------------

class UtilsTestCase(TestCase):
    def test_parse_datetime(self):
        _dt = DT.datetime
        dates = [
            ('Sep 5, 2016', (_dt(2016, 9, 5, 0, 0, 0),
                             _dt(2016, 9, 6, 0, 0, 0))),
            ('5 Sep 2016', (_dt(2016, 9, 5, 0, 0, 0),
                            _dt(2016, 9, 6, 0, 0, 0))),
            ('06/1998', (_dt(1998, 6, 1, 0, 0, 0),
                         _dt(1998, 7, 1, 0, 0, 0))),
            ('Jan 2018 to Oct 2018', (_dt(2018, 1, 1, 0, 0, 0),
                                      _dt(2018, 11, 1, 0, 0, 0))),
            ('1 Jan 2018 to 30 Sep 2018', (_dt(2018, 1, 1, 0, 0, 0),
                                           _dt(2018, 10, 1, 0, 0, 0))),
            ('12/2017', (_dt(2017, 12, 1, 0, 0, 0),
                         _dt(2018, 1, 1, 0, 0, 0))),
            ('2017/12', (_dt(2017, 12, 1, 0, 0, 0),
                         _dt(2018, 1, 1, 0, 0, 0))),
            ('2017/12 to 2018/12', (_dt(2017, 12, 1, 0, 0, 0),
                                    _dt(2019, 1, 1, 0, 0, 0))),
            ('Jan 1, 2017, Jan 1, 2018', (_dt(2017, 1, 1, 0, 0, 0),
                                          _dt(2018, 1, 2, 0, 0, 0))),
            ('to Jan 2018', (None, _dt(2018, 2, 1, 0, 0, 0))),
            ('2015 -', (_dt(2015, 1, 1, 0, 0, 0), None)),
        ]
        for date_str, date_obj in dates:
            with self.subTest(date_str=date_str):
                self.assertEqual(
                    utils.parse_datetime(date_str),
                    date_obj
                )
