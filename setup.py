from setuptools import setup

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(name="oes",
      version="1.0.2",
      description=long_description,
      long_description_content_type="text/markdown",
      url="https://github.com/solstice-ai/optimal-energy-storage",
      author="Julian de Hoog",
      author_email='julian@dehoog.ca',
      license="MIT",
      packages=["oes"],
      install_requires=[
            'pandas',
      ],
      tests_require=[
            'pytest',
            'pandas'
      ],
      zip_safe=False)
