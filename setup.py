# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

with open('requirements.txt') as f:
	install_requires = f.read().strip().split('\n')

# get version from __version__ variable in production_api/__init__.py
from production_api import __version__ as version

setup(
	name='production_api',
	version=version,
	description='Frappe application to manage manufacturing workflows',
	author='Essdee',
	author_email='apps@essdee.dev',
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
