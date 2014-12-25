from distutils.core import setup
from Cython.Build import cythonize

setup(
  name = 'age text function',
  ext_modules = cythonize("age_c.pyx"),
)



#from distutils.core import setup
#from distutils.extension import Extension
#from Cython.Distutils import build_ext
#
#ext_modules = [Extension("age_c", ["age_c.pyx"])]
#
#setup(
#  name = 'age text funct',
#  cmdclass = {'build_ext': build_ext},
#  ext_modules = ext_modules
#)
