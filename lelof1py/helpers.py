import logging
from .definitions import *


SYNC_LOGGER = logging.getLogger(Constants.LOGGER_SYNC_NAME)


def synchronized(lock):
	'''
	Synchronization decorator to manage concurrent access to critical resources
	'''
	
	def synchronized_decorator(f):
		def synchronized_wrapper(*args, **kw):
			_resource_id = lock.__hash__()
			SYNC_LOGGER.debug("acquiring lock for resource {}".format(_resource_id))
			lock.acquire()
			SYNC_LOGGER.debug("lock acquired for resource {}".format(_resource_id))
			try:
				return f(*args, **kw)
			finally:
				SYNC_LOGGER.debug("lock released for resource {}".format(_resource_id))
				lock.release()
		return synchronized_wrapper
	return synchronized_decorator