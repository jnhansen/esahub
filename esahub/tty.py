from .config import CONFIG
import sys
from tqdm import tqdm

BAR_FORMAT = "{desc} {percentage:3.0f}% |{bar}| " \
             "{n_fmt}/{total_fmt} " \
             "[{elapsed}, {rate_fmt: >8}{postfix}]"
# <{remaining}


def shorten(text, maxlen=30):
    if len(text) <= maxlen:
        return text
    else:
        n_end = int((maxlen - 3) / 2)
        n_start = maxlen - 3 - n_end
        return '{}...{}'.format(text[:n_start], text[-n_end:])


class Screen():
    _status = None
    _lines = {}

    def __init__(self, *args, **kwargs):
        self.reset_status(0)

    def reset_status(self, total):
        # status_fmt = ''
        if self._status is not None:
            self._status.close()
            self._status = tqdm(total=total,
                                disable=CONFIG['GENERAL']['QUIET'])

    def __setitem__(self, key, total):
        pass

    def update(self, key, msg):
        if key in self._lines:
            if 'progress' in msg:
                # Update progress bar
                self._lines[key].update(msg['progress'])
            if 'desc' in msg:
                desc = msg['desc'].format(name=shorten(key))
                self._lines[key].set_description_str(desc=desc)
            if 'total' in msg:
                self._lines[key].total = msg['total']
        else:
            # Create new progress bar
            if 'desc' in msg:
                desc = msg['desc'].format(name=shorten(key))
            else:
                desc = 'File {}'.format(len(self._lines) + 1)

            total = msg['total'] if 'total' in msg else None
            self._lines[key] = tqdm(
                desc=desc, total=total, unit='B', unit_scale=True,
                ascii=True, bar_format=BAR_FORMAT,
                mininterval=0.3,
                disable=CONFIG['GENERAL']['QUIET']
            )

    def set_status(self, counter, total=None, msg=None):
        if total is not None:
            self.reset_status(total)
        if msg is not None:
            self._status.desc = msg
        self._status.total

    def quit(self):
        # Close all progress bars
        if self._status is not None:
            del self._status
        for key, pbar in self._lines.items():
            del pbar

    def __del__(self):
        self.quit()


screen = None


def init():
    global screen
    screen = Screen()


def quit():
    global screen
    del screen


def wait_for_quit():
    global screen
    del screen


def update(key, msg):
    global screen
    screen.update(key, msg)


def finish_status():
    pass


def header(text):
    global screen
    screen['header'] = text


def result(text):
    global screen
    screen['result'] = text


def status(text, progress=None):
    global screen
    screen['status'] = text


def set_progress(counter, total):
    global screen


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
    if False and sys.stdout.isatty() and not CONFIG['GENERAL']['USE_GUI']:
        return '{0}{1}{2}{3}'.format(BOLD, RED, message, END)
    else:
        return message


def warn(message):
    if False and sys.stdout.isatty() and not CONFIG['GENERAL']['USE_GUI']:
        return '{0}{1}{2}{3}'.format(BOLD, YELLOW, message, END)
    else:
        return message


def success(message):
    if False and sys.stdout.isatty() and not CONFIG['GENERAL']['USE_GUI']:
        return '{0}{1}{2}{3}'.format(BOLD, GREEN, message, END)
    else:
        return message


init()
