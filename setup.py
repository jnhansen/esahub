# import distutils.cmd
import setuptools
import setuptools.command.build_py
import os
import shutil


def readme():
    with open('README.md') as f:
        return f.read()


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
    cmdclass={
        'build_py': BuildPyCommand,
    },
    name='esahub',
    version='0.1',
    description='A Python module for downloading ESA satellite data',
    long_description=readme(),
    keywords='esahub sentinel satellite',
    url='http://github.com/jnhansen/esahub',
    author='Johannes Hansen',
    author_email='johannes.niklas.hansen@gmail.com',
    license='MIT',
    packages=setuptools.find_packages(),
    install_requires=[
        'pyyaml',
        'numpy',
        'lxml',
        'pyproj',
        'shapely',
        'netCDF4',
        'python-dateutil',
        'pytz',
        'tqdm'
    ],
    setup_requires=['pytest-runner'],
    entry_points={
        'console_scripts': ['esahub=esahub.cli:main'],
    },
    include_package_data=True,
    zip_safe=False,
    tests_require=['pytest']
)
