from .config import CONFIG
import sys
from tqdm import tqdm

BAR_FORMAT = "{desc} {percentage:3.0f}% |{bar}| " \
             "{n_fmt: >5}/{total_fmt: <5} " \
             "[{elapsed}, {rate_fmt: >8}{postfix}]"
NOBAR_FORMAT = "{desc}"
STATUS_RATE_FORMAT = "{desc} {n_fmt} [{elapsed}, {rate_fmt}]"
STATUS_BAR_FORMAT = "{desc} {percentage:3.0f}% |{bar}| [{elapsed}]"
STATUS_NOBAR_FORMAT = "{desc} [{elapsed}]"
FAKE_TOTAL = 9000000000000


def shorten(text, maxlen=30):
    if len(text) <= maxlen:
        return text
    else:
        n_end = int((maxlen - 3) / 2)
        n_start = maxlen - 3 - n_end
        return '{}...{}'.format(text[:n_start], text[-n_end:])


class Screen():
    _status = None
    _result = None
    _lines = {}

    def __init__(self, *args, **kwargs):
        pass

    def status(self, desc=None, mode=None, total=None, progress=None,
               reset=False, unit=None, scale=None):
        if mode is None:
            bar_format = STATUS_NOBAR_FORMAT
        elif mode == 'rate':
            bar_format = STATUS_RATE_FORMAT
        elif mode == 'bar':
            bar_format = STATUS_BAR_FORMAT
        elif mode == 'static':
            bar_format = STATUS_NOBAR_FORMAT
        else:
            bar_format = STATUS_NOBAR_FORMAT
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
            self._result = tqdm(disable=CONFIG['GENERAL']['QUIET'],
                                total=FAKE_TOTAL,
                                desc=text,
                                bar_format=NOBAR_FORMAT,
                                position=len(self._lines) + 1,
                                leave=True)
        else:
            self._result.set_description_str(text)
        # While we are at it, refresh the status.
        self._status.refresh()

    def __getitem__(self, key):
        if key not in self._lines:
            self._lines[key] = tqdm(
                desc='Downloading {name}'.format(name=shorten(key)),
                unit='B', unit_scale=True,
                bar_format=BAR_FORMAT,
                mininterval=0.3,
                disable=CONFIG['GENERAL']['QUIET'],
                position=len(self._lines) + 1,
                leave=True
            )

        return self._lines[key]

    def __setitem__(self, key, text):
        if key == 'result':
            self.result(text)
        elif key == 'status':
            self.screen.status()
            self._status.set_description_str(text)
            self._status.refresh()
        elif key in self._lines:
            self._lines[key].desc = text.format(name=shorten(key))
            self._lines[key].refresh()

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
PURPLE = '\033[95m'
CYAN = '\033[96m'
DARKCYAN = '\033[36m'
BLUE = '\033[94m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BOLD = '\033[1m'
UNDERLINE = '\033[4m'
END = '\033[0m'


def error(message):
    if False and sys.stdout.isatty():
        return '{0}{1}{2}{3}'.format(BOLD, RED, message, END)
    else:
        return message


def warn(message):
    if False and sys.stdout.isatty():
        return '{0}{1}{2}{3}'.format(BOLD, YELLOW, message, END)
    else:
        return message


def success(message):
    if False and sys.stdout.isatty():
        return '{0}{1}{2}{3}'.format(BOLD, GREEN, message, END)
    else:
        return message
