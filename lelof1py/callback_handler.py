import logging
from .definitions import *


class CallbackHandler:
	'''
	Basic class to handle notifications callbacks.
	An instance of this object is returned to caller when subscribing to an event.
	The caller can .unregister using either the client or the returned object.
	'''
	logger = logging.getLogger(Constants.LOGGER_CALLBACK_NAME)

	def __init__(self, original_client, register, user_callback):
		self.original_client = original_client
		self.register = register
		self.user_callback = user_callback

	def activate(self):
		'''
		Activates reception of notifications
		'''
		self.active = True
	
	def deactivate(self):
		'''
		Temporarily deactivates reception of notifications.
		Note that deactivating a callback handler does not unsubscribe at the BLE level.
		BLE-level notifications unsubscription is automatically managed when calling unregister().
		To remove permanently remove subscription use the unregister() method.
		'''
		self.active = False
	
	def is_active(self):
		'''
		Checks wether the callback should receive notification data.
		'''
		return self.active	
		
	async def unregister(self):
		'''
		Permanently deactivates the callback.
		If no other callbacks are still active on the register, unregisters from notifications at BLE-level.
		'''
		return await self.original_client.unregister(self)

	def dispatch(self, data):
		'''
		Dispatch notification data to user-provided callback.
		'''
		if not self.is_active():
			self.logger.warning('dispatch called but handler is not active, skipping')
			return
		if not self.user_callback:
			self.logger.warning('dispatch called but no callback provided, skipping')
			return
		self.logger.debug('dispatching to final user handler started')
		
		try:
			self.user_callback(data)
		except Exception as e:
			self.logger.error('Error dispatching notification to user handler: %s', e)

		self.logger.debug('dispatching to final user handler completed')