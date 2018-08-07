# import distutils.cmd
import setuptools
import setuptools.command.build_py
from distutils.command.clean import clean as Clean
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


class CleanCommand(Clean):
    description = "Remove build artifacts from the source tree"

    def run(self):
        Clean.run(self)
        # Remove c files if we are not within a sdist package
        cwd = os.path.abspath(os.path.dirname(__file__))
        remove_c_files = not os.path.exists(os.path.join(cwd, 'PKG-INFO'))
        if os.path.exists('build'):
            shutil.rmtree('build')
        for root, dirs, files in os.walk('esahub'):
            for filename in files:
                if any(filename.endswith(suffix) for suffix in
                       (".so", ".pyd", ".dll", ".pyc")):
                    os.unlink(os.path.join(root, filename))
                    continue
                extension = os.path.splitext(filename)[1]
                if remove_c_files and extension in ['.c', '.cpp']:
                    pyx_file = str.replace(filename, extension, '.pyx')
                    if os.path.exists(os.path.join(root, pyx_file)):
                        os.unlink(os.path.join(root, filename))
            for dirname in dirs:
                if dirname == '__pycache__':
                    shutil.rmtree(os.path.join(root, dirname))


cmdclass = {
    'clean': CleanCommand,
    'build_py': BuildPyCommand,
}

setuptools.setup(
    use_scm_version=True,
    cmdclass=cmdclass
)
