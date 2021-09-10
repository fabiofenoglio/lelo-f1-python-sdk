from distutils.core import setup


setup(
	name = 'lelof1py',
	packages = ['lelof1py'],
	version = '0.13-beta',
	license = 'MIT',
	description = 'Python client for LELO F1 SDK device',
    long_description = 'See https://github.com/fabiofenoglio/lelo-f1-python-sdk',
	author = 'Fabio Fenoglio',
	author_email = 'development@fabiofenoglio.it',
	url = 'https://github.com/fabiofenoglio/lelo-f1-python-sdk',
	download_url = 'https://github.com/fabiofenoglio/lelo-f1-python-sdk/archive/v0.13-beta.tar.gz',
	keywords = ['LELO', 'BLUETOOTH', 'REMOTE', 'F1S', 'F1SV2'],
	install_requires = [
		'asyncio',
		'bleak',
        'appdirs'
	],
	classifiers = [
        # Chose either "3 - Alpha", "4 - Beta" or "5 - Production/Stable" as the current state of your package
		'Development Status :: 4 - Beta',
		'Intended Audience :: Developers',
		'Topic :: Software Development :: Build Tools',
		'License :: OSI Approved :: MIT License',
		'Programming Language :: Python :: 3.6',
		'Programming Language :: Python :: 3.7',
	],
)
