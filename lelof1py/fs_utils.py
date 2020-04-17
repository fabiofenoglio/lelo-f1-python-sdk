import os
import logging
import pickle
import appdirs

from .definitions import *


class FsUtils:
	'''
	Util class to handle save and restore of application data
	'''
	
	logger = logging.getLogger(Constants.LOGGER_FS_NAME)
	
	def __init__(self, appname):
		self.logger.debug('initializing filestore utils with appname %s', appname)
		self.appauthor = 'LeloF1Py SDK'
		self.appname = appname

	
	def get_connection_profile_path(self):
		'''
		Build the connection profile path for the savefile
		'''
		parent_path = appdirs.user_data_dir(self.appname, self.appauthor)
		os.makedirs(parent_path, exist_ok=True)
		result = parent_path + '/' + 'last_connection_profile.dmp'
		self.logger.debug('connection_profile_path = %s', result)
		return result


	def save_connection_profile(self, profile, safe=False):
		'''
		Attempts to serialize a connection profile to the savefile
		'''
		if not profile:
			raise ValueError('Profile is required.')

		try:
			path = self.get_connection_profile_path()
			self.logger.debug('saving connection profile %s to %s', profile.address, path)
			with open(path, 'wb') as f:
				pickle.dump(profile, f)
				
		except Exception as e:
			self.logger.exception('error while attempting to save connection profile %s to %s: %s', profile.address, path, e)
			if not safe:
				raise e


	def load_connection_profile(self, safe=False):
		'''
		Attempts to load a connection profile from the savefile
		'''
		try:
			path = self.get_connection_profile_path()
			
			if not os.path.exists(path):
				self.logger.debug('no saved connection profile to load in %s', path)
				return None
			
			self.logger.debug('attempting to load connection profile from %s', path)
	
			with open(path, 'rb') as f:
				loaded_obj = pickle.load(f)
				
			return loaded_obj
		
		except Exception as e:
			self.logger.exception('error while attempting to load connection profile from %s: %s', path, e)
			if not safe:
				raise e