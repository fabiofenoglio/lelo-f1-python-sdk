from distutils.core import setup

# read the contents of your README file
from os import path

this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
	name = 'lelof1py',
	packages = ['lelof1py'],
	version = '0.4-alpha',
	license = 'MIT',
	description = 'Python client for LELO F1 SDK device',
    long_description = long_description,
    long_description_content_type = 'text/markdown',
	author = 'Fabio Fenoglio',
	author_email = 'development@fabiofenoglio.it',
	url = 'https://github.com/fabiofenoglio/lelo-f1-python-sdk',
	download_url = 'https://github.com/fabiofenoglio/lelo-f1-python-sdk/archive/v0.4-alpha.tar.gz',
	keywords = ['LELO', 'BLUETOOTH'],
	install_requires = [
		'asyncio',
		'bleak',
        'pysimplegui'
	],
	classifiers = [
        # Chose either "3 - Alpha", "4 - Beta" or "5 - Production/Stable" as the current state of your package
		'Development Status :: 3 - Alpha',
		'Intended Audience :: Developers',
		'Topic :: Software Development :: Build Tools',
		'License :: OSI Approved :: MIT License',
		'Programming Language :: Python :: 3.4',
		'Programming Language :: Python :: 3.5',
		'Programming Language :: Python :: 3.6',
	],
)
