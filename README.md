# esahub: Downloading data from ESA scihub
Author: Johannes Hansen (johannes.hansen@ed.ac.uk)

## <a name="setup"></a>Setup
`esahub` can be easily installed by
```
$ git clone git@git.ichec.ie:EVDC/pyEVDC.git .
$ cd pyEDVC
$ pip install .
```

This will also create a YAML configuration file in `~/.evdc.conf` (unless that file exists) by
copying `config.yaml`. The configuration settings in `~/.evdc.conf` have precedence over the settings
in `config.yaml`.

You should overwrite the required settings in your `~/.evdc.conf`, especially:
* `GENERAL.TMP_DIR`
* `GENERAL.DATA_DIR`
* `GENERAL.LOG_FILE`
* `GENERAL.EMAIL_REPORT_RECIPIENTS`
* `GENERAL.SOLR_CORE`
* `GENERAL.S3_BUCKET`

as well as your login details for SciHub in `SERVERS`.

## <a name="test"></a>Testing the installation
Before you run the tests, make sure you have the following components set up, as the tests will _not_
automatically create these:
* A running Solr instance
* An S3 object store

Further to the configuration in `~/.evdc.conf`, you can set test specific configuration in `evdc.tests.config.set_test_config()`. In particular, you should set up a dedicated Solr core as well as a dedicated S3 bucket for testing. As a safety measure, the Solr core and S3 bucket must contain `test`, otherwise the tests will not execute.

Once everything is set up, run the tests as follows. This will take a while.

The recommended way of running tests is:
```
$ python setup.py nosetests --verbosity=2
```

## <a name="usage"></a>Usage
```
$ pyEVDC [cmd] [args] ...
```

### Available commands:

| Command      | Description
|:-------------|:-----------------------------------------------------------------------------------
| `ls`         | Queries SciHub for archives matching the specified query parameters. Prints the total number of files and data size.
| `get`        | Queries SciHub like `ls`, but then downloads the files.
| `store`      | Like `get`, but immediately indexes and uploads each file to the S3 storage after download.
| `index`      | Extracts the metadata from local `.zip` archives, generates an index and feeds it into a Solr instance.
| `upload`     | Uploads local `.zip` archives to the S3 storage.
| `doctor`     | Checks local `.zip` archives for consistency, either by validating the zip format or by comparing to the MD5 checksum from SciHub. Allows to either delete or repair broken files.
| `daily`      | Convenience command for daily cronjob. Performs the `store` and `index` commands for a predefined command. Also offers the `--email` option for reporting.
| `diff`       | (experimental) Assesses whether the S3 storage, index, and local metadata archive are in sync.


### Options

| Option                                    | Available for   | Description
|:------------------------------------------|:----------------|:------------------------------------
| <code>&lt;SAT&gt;</code>                  | all             | Satellite to query, e.g. S1A, S1B, S2A, S2B, S3A
| <code>-N &#124; --nproc &lt;N&gt;</code>  | all             | number of parallel processes/downloads (defaults to config `GENERAL.N_PROC` and `GENERAL.N_DOWNLOADS`)
| <code>--log</code>                        | all             | write log file
| <code>-d &#124; --dir &lt;DIR&gt;</code>  | all             | raw data directory (defaults to config `GENERAL.TMP_DIR`)
| <code>--target &lt;DIR&gt;</code>         | <code>index&#124;store</code>       | metadata directory (defaults to config `GENERAL.DATA_DIR`)
| <code>--out &lt;FILE&gt;</code>           | <code>ls</code> | write files to JSON
| <code>--in &lt;FILE&gt;</code>            | <code>get&#124;store</code> | read files from JSON
| <code>--mission &lt;MISSION&gt;</code>    | <code>ls&#124;get&#124;store</code> | <code>Sentinel-1&#124;Sentinel-2&#124;Sentinel-3</code> (default: `Sentinel-3`)
| <code>-g &#124; --geo &lt;WKT&gt;</code>  | <code>ls&#124;get&#124;store</code> | geospatial location in WKT format
| <code>--location &lt;LOCATION&gt;</code>  | <code>ls&#124;get&#124;store</code> | location as defined in config `LOCATIONS`
| <code>-A &#124; --from_time &lt;TIME&gt;</code> | <code>ls&#124;get&#124;store</code> | start time in format `%Y-%m-%dT%H:%M:%S.000Z`
| <code>-B &#124; --to_time &lt;TIME&gt;</code>   | <code>ls&#124;get&#124;store</code> | end time in format `%Y-%m-%dT%H:%M:%S.000Z`
| <code>-t &#124; --time &lt;ARG&gt;</code>       | <code>ls&#124;get&#124;store</code> | Convenience wrapper for `--from_time` and `--to_time` <br/> <code>today&#124;yesterday&#124;24h&#124;midnight</code>
| <code>--type &lt;TYPE&gt;</code>                | <code>ls&#124;get&#124;store</code> | e.g. `GRD`
| <code>-q &#124; --query &lt;QUERY&gt;</code>    | <code>ls&#124;get&#124;store</code> | custom query for SciHub, e.g. for single archive: `identifier:...`
| <code>-m &#124; --mode &lt;MODE&gt;</code>      | `doctor`        | <code>zip&#124;file</code>
| <code>--output &#124; -o &lt;FILE&gt;</code>    | `index`         | output file for xml index
| <code>--delete</code>                     | `upload`<br/> `doctor` | delete local files after upload, <br/>delete corrupt files
| <code>--repair</code>                     | `doctor`        | redownload corrupt files
| <code>--email</code>                      | `daily`         | send email report
| <code>--gui</code>                        | `daily`         | use the GUI (by default runs in background)
| <code>--sync</code>                       | `diff`          | Attempt to synchronize the S3 storage with the index and local metadata.


### Daily Workflow
`pyEVDC daily` is meant to be run as a daily cronjob to handle the acquisition and ingestion of new Sentinel data.
Running this command will perform the following actions:
1. Download all Sentinel-3 data from SciHub for the four validation locations in France, Ireland, Italy and Namibia for the 24 hour period between 00:00am of the previous day and 00:00am of the current day.
2. After each file is downloaded, it is extracted to obtain the metadata and uploaded to the S3 storage. Only the metadata is retained on the local machine.
3. When all downloads and uploads are complete, newly available metadata is indexed and ingested into the Solr core.
4. If the `--email` option was specified, an email report will be sent to the recipients as specified in the config file.


### Example Workflow for deviating requirements
A typical workflow (if not using `daily`) may look like the following:
1. List the available data for a location of interest, e.g. `POINT(-0.1 51.5)` (London).
```
$ pyEVDC ls --geo='POINT(-0.1 51.5)'
```
2. Download the data, write a log file.
```
$ pyEVDC get --geo='POINT(-0.1 51.5)' --log
```
3. Extract the metadata from the downloaded archives and feed the index into the Solr instance.
```
$ pyEVDC index
```
4. Upload the data to the S3 storage and delete the local copies. Write a log file.
```
$ pyEVDC upload --delete --log
```


### Further Examples
**Ex 1.** Retrieve the number of archives and total file size of Sentinel-3 archives uploaded to SciHub during the past midnight-to-midnight period intersecting Ireland (only works if `Ireland` is defined in the config item `LOCATIONS`):
```
$ pyEVDC ls -t yesterday --location=Ireland
```

**Ex 2.** Download the archives uploaded yesterday for the four validation locations of the EVDC.
```
$ pyEVDC get -t yesterday --location=Ireland_Mace_Head --location=Namibia_Gobabeb --location=Italy_Rome_Tor_Vergata --location=France_La_Crau
```

**Ex 3.** Query SciHub for all available Sentinel-2 data for Ireland and write the result to a JSON file. Then read that JSON file by the `store` command, thus downloading and storing the specified files. _Note:_ Since the JSON file may be edited manually, this approach offers the most flexibility.
```
$ pyEVDC ls --location=Ireland --mission=Sentinel-2 --out=Sen2_IE.json
$ pyEVDC store --in=Sen2_IE.json --log
```

**Ex 4.** Check all zip archives in a custom directory for MD5 consistency and generate a log file.
```
$ pyEVDC doctor --dir=/path/to/dir/ --mode=md5 --log
```


## <a name="dependencies"></a>Dependencies

### Python packages
* `pyyaml`
* `numpy`
* `lxml`
* `pyproj`
* `shapely`
* `pysolr`
* `netCDF4`
* `python-dateutil`
* `pytz`
* `s3cmd`


### External tools
* [Solr](http://lucene.apache.org/solr/)

### Libraries
* `libgeos_c`
