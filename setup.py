#!/usr/bin/env python

# findsilence - Split long WAV files into tracks
# Copyright (C) 2008 Florian Mayer

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

""" Setup file. """

from setuptools import setup

setup(
    name='findsilence',
    version='0.1',
    description='Split WAV files by silence detection.',
    author='Florian Mayer',
    author_email='flormayer@aim.com',
    url='',
    keywords='wav audio',
    license='GPL',
    zip_safe = True,
    packages=['findsilence'],
    scripts=[ ],
    entry_points = {
        'console_scripts': [
            'findsilence = findsilence.main:main',
            ],
    },
)

