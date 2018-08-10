from .config import CONFIG
import sys
import re
from tqdm import tqdm
from tqdm._utils import _environ_cols_wrapper


tqdm.monitor_interval = 1


def TERM_WIDTH():
    if sys.stdout.isatty():
        return _environ_cols_wrapper()(sys.stdout)
    else:
        return 0


BAR = "{desc} {percentage:3.0f}% |{bar}| " \
      "{n_fmt: >5}/{total_fmt: <5} " \
      "[{elapsed}, {rate_fmt: >8}{postfix}]"
# The explicit width is necessary because tqdm doesn't handle color codes
# correctly.
NOBAR = "{desc: <%d}" % TERM_WIDTH()
STATUS_RATE = "{desc} {n_fmt} [{elapsed}, {rate_fmt}]"
STATUS_BAR = "{desc} {percentage:3.0f}% |{bar}| [{elapsed}]"
STATUS_NOBAR = "{desc} [{elapsed}]"
DESC_LEN = 50
LONG_DESC_LEN = 80
FAKE_TOTAL = 9000000000000
RE_ANSI = re.compile(r"\x1b\[[;\d]*[A-Za-z]")


def shorten(text, maxlen=30):
    if len(text) <= maxlen:
        return text
    else:
        n_end = int((maxlen - 3) / 2)
        n_start = maxlen - 3 - n_end
        return '{}...{}'.format(text[:n_start], text[-n_end:])


def _format_desc(desc, key, long=False):
    # Strip away color control codes for length calculation:
    _stripped = RE_ANSI.sub('', desc)
    current_len = len(_stripped)
    if '{name}' in desc:
        current_len -= len('{name}')
    if long:
        key_len = LONG_DESC_LEN - current_len
    else:
        key_len = DESC_LEN - current_len
    short_file_name = shorten(key, key_len)
    return desc.format(name=short_file_name)


class Screen():
    _status = None
    _result = None
    _lines = {}

    def __init__(self, *args, **kwargs):
        pass

    def status(self, desc=None, mode=None, total=None, progress=None,
               reset=False, unit=None, scale=None):
        if mode is None:
            bar_format = STATUS_NOBAR
        elif mode == 'rate':
            bar_format = STATUS_RATE
        elif mode == 'bar':
            bar_format = STATUS_BAR
        elif mode == 'static':
            bar_format = STATUS_NOBAR
        else:
            bar_format = STATUS_NOBAR
        if self._status is None:
            #
            # Initialize new status bar.
            #
            if total is None:
                total = FAKE_TOTAL
            if progress is None:
                progress = 0
            if unit is None:
                unit = 'B'
            if scale is None:
                scale = True
            self._status = tqdm(total=total, desc=desc,
                                disable=CONFIG['GENERAL']['QUIET'],
                                bar_format=bar_format,
                                initial=progress,
                                unit=unit, unit_scale=scale,
                                mininterval=1, maxinterval=1,
                                position=0,
                                leave=True)

        else:
            #
            # Update existing status bar.
            #
            if desc is not None:
                self._status.set_description_str(desc)
            if mode is not None:
                self._status.bar_format = bar_format
            if total is not None:
                self._status.total = total
            if progress is not None:
                self._status.update(progress)
            if reset:
                self._status.n = 0
            if unit is not None:
                self._status.unit = unit
            if scale is not None:
                self._status.unit_scale = scale

            self._status.refresh()

    def result(self, text):
        # Should only be called after all progress bars have been created.
        if self._result is None:
            try:
                disable = CONFIG['GENERAL']['QUIET']
            except TypeError:
                disable = False
            self._result = tqdm(disable=disable,
                                total=FAKE_TOTAL,
                                desc=text,
                                bar_format=NOBAR,
                                position=len(self._lines) + 1,
                                leave=True)
        else:
            self._result.set_description_str(text)

    def __getitem__(self, key):
        if key not in self._lines:
            self._lines[key] = tqdm(
                desc=_format_desc('Downloading {name}', key),
                unit='B', unit_scale=True,
                bar_format=BAR,
                mininterval=0.3, maxinterval=1,
                disable=CONFIG['GENERAL']['QUIET'],
                position=len(self._lines) + 1,
                leave=True
            )

        return self._lines[key]

    def __setitem__(self, key, value):
        pbar = self.__getitem__(key)
        if isinstance(value, tuple):
            value, fmt = value
            pbar.bar_format = fmt
            if pbar.total is None:
                pbar.total = FAKE_TOTAL
        pbar.desc = _format_desc(value, key)
        pbar.refresh()

    def quit(self):
        # Close all progress bars
        if self._result is None:
            self.result('done.')
        if self._status is not None:
            del self._status
        keys = list(self._lines.keys())
        for key in keys:
            del self._lines[key]
        if not self._result.disable:
            # NOTE: The following line is required to put the cursor at the end
            # of the progress bars upon termination. No idea why! :-(
            self._result.moveto(1 - self._result.pos)
        del self._result

    def __del__(self):
        self.quit()


screen = Screen()


# TERMINAL OUTPUT FORMATTING
# -----------------------------------------------------------------------------
ANSI = dict(
    PURPLE='\033[95m',
    CYAN='\033[96m',
    DARKCYAN='\033[36m',
    BLUE='\033[94m',
    GREEN='\033[92m',
    YELLOW='\033[93m',
    RED='\033[91m',
    BOLD='\033[1m',
    UNDERLINE='\033[4m',
    END='\033[0m'
)


def error(message):
    if sys.stdout.isatty():
        return '{BOLD}{RED}{text}{END}'.format(text=message, **ANSI)
    else:
        return message


def warn(message):
    if sys.stdout.isatty():
        return '{BOLD}{YELLOW}{text}{END}'.format(text=message, **ANSI)
    else:
        return message


def success(message):
    if sys.stdout.isatty():
        return '{BOLD}{GREEN}{text}{END}'.format(text=message, **ANSI)
    else:
        return message
