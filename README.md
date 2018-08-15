[![Build Status](https://travis-ci.com/jnhansen/esahub.svg?token=VQTSyenCpuXDiRgpEoZN&branch=master)](https://travis-ci.com/jnhansen/esahub)
[![PyPI version](https://badge.fury.io/py/esahub.svg)](https://badge.fury.io/py/esahub)

# esahub: Downloading data from ESA scihub
`esahub` provides a simple interface for downloading satellite data from the European Sentinel missions.

It allows multiple downloads to be performed in parallel, from multiple data servers.
The full range of Copernicus data servers are supported, including:
* `https://scihub.copernicus.eu/dhus`
* `https://scihub.copernicus.eu/apihub`
* `https://scihub.copernicus.eu/s3` (guest access)
* `https://s5phub.copernicus.eu/dhus` (guest access)
* `https://tmphub.copernicus.eu/dhus`
* `https://colhub.copernicus.eu/dhus`
* `https://colhub2.copernicus.eu/dhus`


## <a name="setup"></a>Setup
Install `esahub`:
```
$ pip install esahub
```

This will also create a YAML configuration file in `~/.esahub.conf` (unless that file exists) by copying `config.yaml`. The configuration settings in `~/.esahub.conf` have precedence over the settings in `config.yaml`.

You should overwrite the required settings in your `~/.esahub.conf`, especially:
* `GENERAL.DATA_DIR`

For the majority of the data servers you will need to provide your own authentication details in `SERVERS`.


## <a name="test"></a>Testing the installation
The recommended way of running tests is:
```
$ python setup.py test
```

*Note:* Running the tests may take a while as it includes testing live downloads from SciHub (although with very small files).

## <a name="usage"></a>Command Line Usage
```
$ esahub [cmd] [args] ...
```

### Available commands:

| Command      | Description
|:-------------|:-----------------------------------------------------------------------------------
| `ls`         | Queries SciHub for archives matching the specified query parameters. Prints the total number of files and data size.
| `get`        | Queries SciHub like `ls`, but then downloads the files.
| `doctor`     | Checks local satellite products for consistency, either by validating the zip/NetCDF format or by comparing to the MD5 checksum from SciHub. Allows to either delete or repair broken files.


### Options

| Option           | Argument                      | Available for | Description
|:-----------------|:------------------------------|:--------------|:------------------
|                  | <code>&lt;SAT&gt;</code>      | all           | Satellite to query, e.g. S1A, S1B, S2A, S2B, S3A
| `-d`, `--dir`    | <code>&lt;DIR&gt;</code>      | all           | raw data directory (defaults to config `GENERAL.DATA_DIR`)
| `-o`, `--out`    | <code>&lt;FILE&gt;</code>     | `ls`          | write files to JSON
| `-i`, `--in`     | <code>&lt;FILE&gt;</code>     | `get`         | read files from JSON
| `-m`, `--mission`| <code>&lt;MISSION&gt;</code>  | `ls`, `get`   | e.g. `Sentinel-1`, `Sentinel-2`, `Sentinel-3`
| `-g`, `--geo`    | <code>&lt;WKT&gt;</code>      | `ls`, `get`   | geospatial location in WKT format
| `--location`     | <code>&lt;LOCATION&gt;</code> | `ls`, `get`   | location as defined in config `LOCATIONS`
| `-t`, `--time`   | <code>&lt;ARG&gt;</code>      | `ls`, `get`   | Supports a variety of datetime string formats.
| `--type`         | <code>&lt;TYPE&gt;</code>     | `ls`, `get`   | e.g. `GRD`
| `--orbit`        | <code>&lt;ORBIT&gt;</code>    | `ls`, `get`   | `ASC` or `DESC`
| `--id`           | <code>&lt;ID&gt;</code>       | `ls`, `get`   | product identifier, may include wildcards (`*`), e.g. `*SDV*`
| `-q`, `--query`  | <code>&lt;QUERY&gt;</code>    | `ls`, `get`   | custom query for SciHub, e.g. for single archive: `identifier:...`
| `--restart`      |                               | `get`         | Force restart incomplete downloads
| `--log`          |                               | all           | write log file
| `--quiet`        |                               | all           | Suppress terminal output
| `--mode`         | <code>&lt;MODE&gt;</code>     | `doctor`      | <code>zip&#124;file</code>
| `--delete`       |                               | `doctor`      | delete corrupt files
| `--repair`       |                               | `doctor`      | redownload corrupt files
| `--email`        |                               | all         | send email report


##### Datetime parsing
The following are examples of datetime formats that will be automatically parsed into a date or date range:

The following single dates will be explicitly converted to the date range covering the given year, month, or day:
* `--time 2016`
* `--time 06/2018`
* `--time 2018/06`
* `--time "Sep 1, 2018"`

Date ranges may also be specified explicitly:
* `--time "2016 to 2017"`
* `--time "Jan 2016 - Feb 2016"`
* `--time "01/01/2016, 14/01/2016"`

One-sided date ranges are also possible:
* `--time "to 2017"`
* `--time "01/2017-"`
* `--time "01/12/2017,"`


### Examples
**Ex 1.** Retrieve the number of archives and total file size of Sentinel-3 archives uploaded to SciHub during the past midnight-to-midnight period intersecting Ireland (only works if `Ireland` is defined in the config item `LOCATIONS`):
```
$ esahub ls -t yesterday --location=Ireland
```

**Ex 2.** Download the archives uploaded yesterday for four locations.
```
$ esahub get -t yesterday --location=Ireland_Mace_Head --location=Namibia_Gobabeb --location=Italy_Rome_Tor_Vergata --location=France_La_Crau
```

**Ex 3.** Query SciHub for all available Sentinel-2 data for Ireland and write the result to a JSON file. Then read that JSON file by the `get` command, thus downloading the specified files. _Note:_ Since the JSON file may be edited manually, this approach offers the most flexibility.
```
$ esahub ls --location=Ireland --mission=Sentinel-2 --out=Sen2_IE.json
$ esahub get --in=Sen2_IE.json --log
```

**Ex 4.** Check all zip archives in a custom directory for MD5 consistency and generate a log file.
```
$ esahub doctor --dir=/path/to/dir/ --mode=md5 --log
```


## Python API
```python
from esahub import scihub
query = {'mission': 'Sentinel-1',
         'geo': 'POINT(-9.0 53.0)',
         'time': 'today'}
files = scihub.search(query)
scihub.download(files)
```


## <a name="dependencies"></a>Dependencies

### Required
* `pyyaml`
* `numpy`
* `lxml`
* `shapely`
* `python-dateutil`
* `pytz`
* `tqdm`

### Optional
* `pyproj`
* `netCDF4`

### Libraries
* `libgeos_c`
