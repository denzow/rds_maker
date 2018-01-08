# coding: utf-8

from setuptools import setup, find_packages
from rds_maker import __VERSION__


with open('README.md') as f:
    readme = f.read()

with open('LICENSE') as f:
    license_txt = f.read()

setup(
    name='rdsmaker',
    version=__VERSION__,
    description='thin wrapper boto3 for RDS.',
    long_description=readme,
    author='denzow',
    author_email='denzow@gmail.com',
    url='https://github.com/denzow/rds_maker',
    license=license_txt,
    packages=find_packages(exclude=('example',))
)
