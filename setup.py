from setuptools import setup

setup(name="oes",
      version="0.7.2",
      description="Optimal operation of energy storage",
      url="https://github.com/solstice-ai/optimal-energy-storage",
      author="Julian de Hoog",
      author_email='julian@dehoog.ca',
      license="Apache-2.0",
      packages=["oes"],
      install_requires=[
            'pandas',
      ],
      tests_require=[
            'pytest',
            'pandas'
      ],
      zip_safe=False)
