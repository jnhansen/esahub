[![Build Status](https://travis-ci.com/jnhansen/esahub.svg?token=VQTSyenCpuXDiRgpEoZN&branch=master)](https://travis-ci.com/jnhansen/esahub)

# esahub: Downloading data from ESA scihub
Author: Johannes Hansen (johannes.hansen@ed.ac.uk)

## <a name="setup"></a>Setup
Install `esahub`:
```
$ pip install esahub
```

This will also create a YAML configuration file in `~/.esahub.conf` (unless that file exists) by
copying `config.yaml`. The configuration settings in `~/.esahub.conf` have precedence over the settings
in `config.yaml`.

You should overwrite the required settings in your `~/.esahub.conf`, especially:
* `GENERAL.DATA_DIR`
* `GENERAL.LOG_FILE`
* `GENERAL.EMAIL_REPORT_RECIPIENTS`

The full range of Copernicus data servers are supported, including:
* `https://scihub.copernicus.eu/dhus`
* `https://scihub.copernicus.eu/apihub`
* `https://scihub.copernicus.eu/s3` (guest access)
* `https://s5phub.copernicus.eu/dhus` (guest access)
* `https://tmphub.copernicus.eu/dhus`
* `https://colhub.copernicus.eu/dhus`
* `https://colhub2.copernicus.eu/dhus`

For the majority of these you will need to provide your own authentication details
in `SERVERS`.


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
| `doctor`     | Checks local `.zip` archives for consistency, either by validating the zip format or by comparing to the MD5 checksum from SciHub. Allows to either delete or repair broken files.


### Options

| Option                                    | Available for   | Description
|:------------------------------------------|:----------------|:------------------------------------
| <code>&lt;SAT&gt;</code>                  | all             | Satellite to query, e.g. S1A, S1B, S2A, S2B, S3A
| <code>-N &#124; --nproc &lt;N&gt;</code>  | all             | number of parallel processes/downloads (defaults to config `GENERAL.N_PROC` and `GENERAL.N_DOWNLOADS`)
| <code>--log</code>                        | all             | write log file
| <code>-d &#124; --dir &lt;DIR&gt;</code>  | all             | raw data directory (defaults to config `GENERAL.DATA_DIR`)
| <code>--out &lt;FILE&gt;</code>           | <code>ls</code> | write files to JSON
| <code>--in &lt;FILE&gt;</code>            | <code>get</code> | read files from JSON
| <code>--mission &lt;MISSION&gt;</code>    | <code>ls&#124;get</code> | <code>Sentinel-1&#124;Sentinel-2&#124;Sentinel-3</code> (default: `Sentinel-3`)
| <code>-g &#124; --geo &lt;WKT&gt;</code>  | <code>ls&#124;get</code> | geospatial location in WKT format
| <code>--location &lt;LOCATION&gt;</code>  | <code>ls&#124;get</code> | location as defined in config `LOCATIONS`
| <code>-A &#124; --from_time &lt;TIME&gt;</code> | <code>ls&#124;get</code> | start time in format `%Y-%m-%dT%H:%M:%S.000Z`
| <code>-B &#124; --to_time &lt;TIME&gt;</code>   | <code>ls&#124;get</code> | end time in format `%Y-%m-%dT%H:%M:%S.000Z`
| <code>-t &#124; --time &lt;ARG&gt;</code>       | <code>ls&#124;get</code> | Convenience wrapper for `--from_time` and `--to_time` <br/> <code>today&#124;yesterday&#124;24h&#124;midnight</code>
| <code>--type &lt;TYPE&gt;</code>                | <code>ls&#124;get</code> | e.g. `GRD`
| <code>-q &#124; --query &lt;QUERY&gt;</code>    | <code>ls&#124;get</code> | custom query for SciHub, e.g. for single archive: `identifier:...`
| <code>-m &#124; --mode &lt;MODE&gt;</code>      | `doctor`        | <code>zip&#124;file</code>
| <code>--delete</code>                     | `doctor`        | delete corrupt files
| <code>--repair</code>                     | `doctor`        | redownload corrupt files
| <code>--email</code>                      | `all`         | send email report
| <code>--gui</code>                        | `all`         | use the GUI (by default runs in background)


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
scihub.download_many(files)
```


## <a name="dependencies"></a>Dependencies

### Python packages
* `pyyaml`
* `numpy`
* `lxml`
* `pyproj`
* `shapely`
* `netCDF4`
* `python-dateutil`
* `pytz`
* `tqdm`

### Libraries
* `libgeos_c`
