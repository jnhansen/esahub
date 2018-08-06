# import distutils.cmd
import setuptools
import setuptools.command.build_py
import os
import shutil


def init_config():
    src = 'esahub/config.yaml'
    dst = os.path.expanduser('~/.esahub.conf')
    if not os.path.isfile(dst):
        shutil.copyfile(src, dst)


class BuildPyCommand(setuptools.command.build_py.build_py):
    """Custom build command."""

    def run(self):
        init_config()
        setuptools.command.build_py.build_py.run(self)


setuptools.setup(
    use_scm_version=True,
    cmdclass={
        'build_py': BuildPyCommand,
    }
)
