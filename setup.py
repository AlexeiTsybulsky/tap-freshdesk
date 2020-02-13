#!/usr/bin/env python

from setuptools import setup

setup(name='tap-freshdesk',
      version='0.10.0',
      description='Singer.io tap for extracting data from the Freshdesk API',
      author='Stitch',
      url='http://singer.io',
      classifiers=['Programming Language :: Python :: 3 :: Only'],
      py_modules=['tap_freshdesk'],
      install_requires=[
          'singer-python==5.8.0',
          'requests==2.20.0',
          'backoff==1.8.0'
      ],
      entry_points='''
          [console_scripts]
          tap-freshdesk=tap_freshdesk:main
      ''',
      packages=['tap_freshdesk'],
      package_data = {
          'tap_freshdesk/schemas': [
              'ticket_activities.json'
          ],
      },
      include_package_data=True,
)
