import logging
from .definitions import *


class Register:
	'''
	Basic class to handle device registers.
	
	A register is a combination of:
	- characteristic
	- data converter for READ
	- data converter for WRITE
	'''
	logger = logging.getLogger(Constants.LOGGER_IO_NAME)


	def __init__(self, name, address, translator_from, translator_to):
		self.name = name
		self.address = address
		self.translator_from = translator_from
		self.translator_to = translator_to


	def from_device(self, value, silent=False):
		'''
		Translates a device byte value to an usable value
		'''
		if not silent:
			self.logger.debug('translating value %s from device register %s', value, self.name)
		v = self.translator_from(value)
		if not silent:
			self.logger.debug('translated value from device register %s to %s', self.name, v)
		return v


	def to_device(self, value, silent=False):
		'''
		Translates the local usable value to device byte value
		'''
		if not silent:
			self.logger.debug('translating value %s to device register %s bytes', value, self.name)
		v = self.translator_to(value)
		if not silent:
			self.logger.debug('translated value to device register %s bytes %s', self.name, v)
		return v