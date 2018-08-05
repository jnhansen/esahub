import unittest
import contextlib
import logging
import re
import datetime as DT
import pytz
import os
import sys
import shutil
import subprocess
from esahub.tests import config as test_config
from esahub import config
from esahub import geo, helpers, scihub, checksum, check, main

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
            yield
            return


# -----------------------------------------------------------------------------
# TEST SETUP
# -----------------------------------------------------------------------------
def setUpModule():
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
        # for name, auth in config.CONFIG['SERVERS'].items():
        for name in ['DHUS', 'S3', 'S2B', 'COLHUB1', 'COLHUB2']:
            auth = config.CONFIG['SERVERS'][name]
            conn = scihub.Connection(**auth)
            with self.subTest(server_name=name):
                # url = scihub_connect.Query().build_query_url()
                url = '{}/search?q=*:*'.format(auth['host'])
                result = conn.resolve(url)
                #
                # Assert that the HTML response has status code 200 (OK)
                #
                self.assertEqual(result.code, 200)

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
            ({'mission': 'Sentinel-1'}, ['COLHUB2', 'COLHUB1', 'DHUS']),
            ({'mission': 'Sentinel-2'}, ['COLHUB2', 'COLHUB1', 'DHUS']),
            ({'mission': 'Sentinel-3'}, ['COLHUB2', 'COLHUB1', 'S3']),
            ({'satellite': 'S1A'}, ['COLHUB2', 'COLHUB1', 'DHUS']),
            ({'satellite': 'S3A'}, ['COLHUB2', 'COLHUB1', 'S3']),
            ({'satellite': 'S2B'}, ['COLHUB2', 'COLHUB1', 'DHUS']),
            ({'identifier': "S1A_IW_OCN__2SDV_20160924T181320_"
                            "20160924T181345_013198_014FDF_6692.zip"},
             ['COLHUB2', 'COLHUB1', 'DHUS']),
        ]
        for query, server in queries:
            with self.subTest(query=query):
                self.assertEqual(
                    scihub._auto_detect_server_from_query(query), server
                )

    def test__uuid_from_identifier(self):
        uuids = [
            ("S1A_IW_OCN__2SDV_20180322T154129_20180322T154143_"
             "021129_024501_28FF", "6ea4eb6e-4775-4fd5-bfca-8302470eddea"),
            ("S1B_IW_OCN__2SDV_20180319T045826_20180319T045840_"
             "010096_01252B_F351", "03131fb7-f6ad-4ca3-ae69-603a31a7d392"),
            ("S2A_MSIL1C_20180328T125131_N0206_R138_T29WPT_20180328T195708",
             "defbc2cc-0537-4303-b7e2-60586e715c49"),
            ("S2B_MSIL1C_20180325T234129_N0206_R030_T60UVC_20180326T011902",
             "a0eb98fb-0379-4af3-a288-5f0dedbfaac4"),
            # ("S3A_OL_1_EFR____20180328T071326_20180328T071326_"
            #  "20180328T094706_0000_029_234_3960_SVL_O_NR_002",
            #  "39c4d7ac-0c81-4689-9858-e3429f48b078"),
        ]
        for product, uuid in uuids:
            with self.subTest(product=product):
                self.assertEqual(
                    scihub._uuid_from_identifier(product), uuid
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

    def test_resolve(self):
        for name in ['DHUS', 'S3', 'S2B']:
            with self.subTest(server_name=name):
                response = scihub.resolve(
                    scihub._build_url({'query': '*:*'}, name)
                )
                self.assertEqual(response.code, 200)

    def test_md5_from_file(self):
        for f in helpers.ls(config.CONFIG['GENERAL']['DATA_DIR']):
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
        url = scihub._build_url({'mission': 'Sentinel-1'}, 'DHUS')
        result = scihub.resolve(url)
        html = result.read()
        #
        # Assert that the number of entries found on the page matches the
        # number of entries requested per page.
        #
        self.assertEqual(html.count(b'<entry>'),
                         config.CONFIG['GENERAL']['ENTRIES'])

    def test_queries(self):
        queries = [
            # (name, query, server)
            ('S1', {'mission': 'Sentinel-1'}, 'DHUS'),
            ('S2', {'mission': 'Sentinel-2'}, 'DHUS'),
            ('S3', {'mission': 'Sentinel-3'}, 'S3'),
        ]
        for name, q, server in queries:
            with self.subTest(name=name):
                url = scihub._build_url(q, server=server)
                result = scihub.resolve(url)
                #
                # Assert that queries for each mission return a
                # status code 200 (OK)
                #
                self.assertEqual(result.code, 200)

        with self.subTest('count entries'):
            q = {'mission': 'Sentinel-1'}
            url = scihub._build_url(q, server='DHUS')
            result = scihub.resolve(url)
            html = result.read()
            #
            # Assert that the number of entries found on the page matches the
            # number of entries requested per page.
            #
            self.assertEqual(html.count(b'<entry>'),
                             config.CONFIG['GENERAL']['ENTRIES'])

    def test_temporal_queries(self):
        with self.subTest('yesterday'):
            file_list = scihub.search({'mission': 'Sentinel-1',
                                       'time': 'yesterday', 'type': 'GRD'},
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
            file_list = scihub.search({'mission': 'Sentinel-1',
                                       'time': 'today', 'type': 'GRD'},
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
                {'location': [loc], 'to_time': '2017-09-01T00:00:00Z'},
                server='S3', limit=20)
            for f in file_list:
                with self.subTest(product=f['filename']):
                    #
                    # Assert that the products indeed intersect the
                    # requested location.
                    #
                    self.assertTrue(geo.intersect(f['coords'], ref_coords,
                                                  tolerance=0.1))

    def test_get_file_list(self):
        q = {'mission': 'Sentinel-1'}
        limit = 107
        file_list = scihub.search(q, server='DHUS', limit=limit)
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
        scihub.download_many(file_list)
        #
        # Assert that all downloads were successful.
        #
        local_files = helpers.ls(config.CONFIG['GENERAL']['DATA_DIR'])
        local_files_identifiers = [os.path.splitext(os.path.split(_)[1])[0]
                                   for _ in local_files]
        for f in file_list:
            self.assertIn(f['filename'], local_files_identifiers)
        for f in local_files:
            with self.subTest(file=f):
                _, healthy, _ = check.check_file(f, mode='md5')
                self.assertTrue(healthy)

    def test_redownload(self):
        test_config.copy_corrupt_data()
        local_files = helpers.ls(config.CONFIG['GENERAL']['DATA_DIR'])
        scihub.redownload(local_files)
        new_local_files = helpers.ls(config.CONFIG['GENERAL']['DATA_DIR'])
        self.assertEqual(set(local_files), set(new_local_files))
        for f in local_files:
            with self.subTest(file=f):
                _, healthy, _ = check.check_file(f, mode='md5')
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
        for f in helpers.ls(config.CONFIG['GENERAL']['DATA_DIR']):
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
        for f in helpers.ls(config.CONFIG['GENERAL']['DATA_DIR']):
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
        for f in helpers.ls(config.CONFIG['GENERAL']['DATA_DIR']):
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
        for f in helpers.ls(config.CONFIG['GENERAL']['DATA_DIR']):
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
        for f in helpers.ls(config.CONFIG['GENERAL']['DATA_DIR']):
            with self.subTest(file=f):
                #
                # Assert that the md5 checksum returned by checksum.md5() is
                # equal to the md5 sum returned by bash md5 or md5sum tool.
                #
                for exe in ['md5', 'md5sum']:
                    if shutil.which(exe):
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
        for f in helpers.ls(config.CONFIG['GENERAL']['DATA_DIR']):
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
        corrupt_files = helpers.ls(test_config.TEST_DATA_DIR_CORRUPT,
                                   path=False)
        healthy_files = helpers.ls(test_config.TEST_DATA_DIR_ORIGINAL,
                                   path=False)
        main.doctor()
        #
        # Assert that the number of healthy/corrupt files detected are correct
        #
        self.assertEqual(check.BAD_FILE_COUNTER, len(corrupt_files))
        self.assertEqual(check.FILE_COUNTER,
                         len(corrupt_files) + len(healthy_files))
        bad_files = [os.path.split(_)[1] for _ in check.BAD_FILES]
        for corrupt_file in corrupt_files:
            #
            # Assert that each corrupt file has been registered.
            #
            self.assertIn(corrupt_file, bad_files)

    def test_doctor_delete(self):
        test_config.copy_corrupt_data()
        corrupt_files = helpers.ls(test_config.TEST_DATA_DIR_CORRUPT,
                                   path=False)
        healthy_files = helpers.ls(test_config.TEST_DATA_DIR_ORIGINAL,
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
        corrupt_files = helpers.ls(test_config.TEST_DATA_DIR_CORRUPT,
                                   path=False)
        # healthy_files = helpers.ls(test_config.TEST_DATA_DIR_ORIGINAL,
        #                            path=False)
        main.doctor(repair=True)

        for f in corrupt_files:
            repaired_f = os.path.join(config.CONFIG['GENERAL']['DATA_DIR'], f)
            with self.subTest(file=repaired_f):
                #
                # Assert that each corrupt file has been repaired.
                #
                _, healthy, _ = check.check_file(repaired_f, mode='file')
                self.assertTrue(healthy)


# -----------------------------------------------------------------------------
# HELPERS
# -----------------------------------------------------------------------------

# class HelpersTestCase(TestCase):
#
#     def setUp(self):
#         test_config.set_test_config()
#         test_config.copy_test_data()
#
#     def tearDown(self):
#         test_config.clear_all()