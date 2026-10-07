from pathlib import Path
from setuptools import Extension, setup
from setuptools.command.build_ext import build_ext

base = Path(__file__).absolute().parent
class FlatBuildExt(build_ext):
    def build_extension(self, ext):
        original = self.compiler.object_filenames
        def flat_object_filenames(sources, strip_dir=0, output_dir=None):
            folder = Path(output_dir or self.build_temp)
            return [str(folder / (Path(source).stem + ".obj")) for source in sources]
        self.compiler.object_filenames = flat_object_filenames
        try:
            super().build_extension(ext)
        finally:
            self.compiler.object_filenames = original

setup(name="surface-prefilter-baseline", ext_modules=[Extension("_surface_prefilter_old", [str(base / "baseline.c")], extra_compile_args=["/fp:strict", "/utf-8"])], cmdclass={"build_ext": FlatBuildExt})
