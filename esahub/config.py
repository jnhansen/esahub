import yaml
import os

SETTINGS_FILES = [
    os.path.join(os.path.dirname(__file__), 'config.yaml'),
    os.path.expanduser('~/.esahub.conf')
]
CONFIG = {}


#
# Settings files in order of increasing precedence
#
def load(fname):
    fname = os.path.expanduser(fname)
    if os.path.isfile(fname):
        with open(fname, 'r') as fid:
            CONFIG.update(yaml.load(fid))
    CONFIG['GENERAL']['DATA_DIR'] = \
        os.path.expanduser(CONFIG['GENERAL']['DATA_DIR'])


for f in SETTINGS_FILES:
    load(f)
