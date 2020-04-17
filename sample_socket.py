import asyncio
import logging
import socket
import json
import PySimpleGUI as sg
from collections.abc import Sequence
import threading
import time

import lelof1py as f1client

from sample_gui import GUISample


LISTEN_ADDR = '0.0.0.0'
LISTEN_PORT = 5005
SOCKET_ENCODING = 'utf8'


class SampleClient:
	'''
	Holds information for connected clients.
	'''

	id = None
	name = None
	authorized = False
	locking = False

	def __init__(self, id):
		self.id = id
		
	def is_authorized(self):
		return self.authorized
	
	def authorize(self):
		self.authorized = True


# Initialize context with service
class GUISampleWithSocket(GUISample):
	'''
	Complete sample of device discovery, connection and control with simple GUI.
	Includes a socket server for remote control
	'''
	def __init__(self, loop, refresh_interval=1/100):
		super(GUISampleWithSocket, self).__init__(loop, refresh_interval)

		logging.info('running GUISampleWithSocket in event loop %s', loop)
		
		# t = threading.Thread(target=self.server_runner)
		# t.start()
		# self.server_thread = t
		self.server_thread = None
		
		self.tasks.append(loop.create_task(self.server_runner()))

	
	async def server_runner(self):
		try:
			# l = asyncio.new_event_loop()
			l = asyncio.get_event_loop()

			logging.info('running server_runner in event loop %s', l)
			
			# Register an additional task to listen for socket data
			self.server = f1client.SocketServer(self.get_client, LISTEN_ADDR, LISTEN_PORT)
			
			self.server.set_authorization_handler(self.prompt_authorization)
			self.server.set_command_handler(self.execute_command)
			self.server.on_client_disconnect(self.client_disconnect)
			self.server.on_client_connected(self.client_connected)
			self.server.on_after_command(self.after_command)
			
			# logging.info('starting server in new server_runner thread')
			logging.info('starting server in current loop')
			self.server_loop = l
			
			# self.tasks.append(task)
			# logging.debug('waiting for server_runner loop to run_forever')
			# l.run_until_complete(self.server.run_server(l))
			await self.server.run_server(l)
			
			# logging.debug('closing server_runner loop')
			# l.close()
			# logging.debug('done closing server_runner loop')
	
		except Exception as e:
			if self.server and self.server.stopped:
				logging.warn('error in server_runner: %s', e)
			else:
				logging.exception('error in server_runner: %s', e)


	def handle_event(self, event):
		'''
		Dispatch button event if and only if control is not locked from client.
		'''
		if self.is_locked_from_client():
			logging.debug('ignoring button event because control is locked')
			self.log('you do not have control of your device!')
		else:
			return super(GUISampleWithSocket, self).handle_event(event)


	def is_locked_from_client(self):
		'''
		Checks wether a client has revoked local control
		'''
		for client in self.server.get_active_clients():
			if client.locking:
				return True
			
		return False


	async def after_command(self, client_info, command, arguments, result):
		
		for p in ['enable_', 'disable_', 'reset_', 'enter_']:
			if command.startswith(p):
				self.log((client_info.name or client_info.id) + ' sent ' + command)
				self.schedule(self.refresh_status(), name='refresh_status', locking=False)
				break


	async def client_connected(self, client_info):
		'''
		Callback for client connection
		'''
		self.log( (client_info.name or client_info.id) + ' CONNECTED')


	async def client_disconnect(self, client_info):
		'''
		Callback for client disconnection
		'''
		self.log( (client_info.name or client_info.id) + ' DISCONNECTED')
		
		if not self.is_locked_from_client():
			await self.unlock()


	async def execute_command(self, client_info, command, arguments):
		'''
		Handle arbitrary commands.
		Should return a touple (handled, result).
		'''
		if hasattr(self, 'command_' + command):
			return (True, await getattr(self, 'command_' + command)(client_info, arguments))
		
		else:
			return (False, None)


	async def command_lock(self, client_info, arguments):
		'''
		User can no longer control his device.
		'''
		self.server.assert_authorized(client_info)

		if client_info.locking:
			logging.debug('client is locking already')
			return

		self.log((client_info.name or client_info.id) + ' has revoked control of your device!') 
		client_info.locking = True

		if self.is_locked_from_client():
			self.lock()
		
		
	async def command_unlock(self, client_info, arguments):
		'''
		Restore user control on his device.
		'''
		self.server.assert_authorized(client_info)
		
		if not client_info.locking:
			raise ValueError('Client was not locking')
		
		self.log((client_info.name or client_info.id) + ' has granted you control of your device!') 
		client_info.locking = False
		
		if not self.is_locked_from_client():
			await self.unlock()


	async def command_get_status_snapshot(self, client_info, arguments):
		'''
		Gets the latest status snapshot
		'''
		self.server.assert_authorized(client_info)
		return self.snapshot


	async def prompt_authorization(self, client_info, arguments):
		'''
		Requests user authorization if needed
		'''
		identifier = client_info.name or client_info.id
		
		window = sg.Window('Remote control request', [[sg.Text(identifier + ' asked to control your device. Do you want to allow it?', pad=(0, 20))],
			[sg.Button('Deny', key='deny', size=(10, None)), sg.Button('Allow', key='allow', size=(10, None))]])
		
		result = False
		
		while True:
			window.refresh()
			event, _ = window.read(timeout=10)
			
			if event is None or event != '__TIMEOUT__':
				if event is None or event == 'deny':
					break
				elif event == 'allow':
					result = True
					break

			await asyncio.sleep(0.1)

		window.close()
		return result


	async def command_shutdown_main_motor(self, client_info, arguments):
		'''
		Dispatch to local handler
		'''
		return await self.shutdown_main_motor()

	
	async def command_decrement_main_motor(self, client_info, arguments):
		'''
		Dispatch to local handler
		'''
		return await self.decrement_main_motor()


	async def command_increment_main_motor(self, client_info, arguments):
		'''
		Dispatch to local handler
		'''
		return await self.increment_main_motor()

	
	async def command_shutdown_vibe_motor(self, client_info, arguments):
		'''
		Dispatch to local handler
		'''
		return await self.shutdown_vibe_motor()
	
	
	async def command_decrement_vibe_motor(self, client_info, arguments):
		'''
		Dispatch to local handler
		'''
		return await self.decrement_vibe_motor()

	
	async def command_increment_vibe_motor(self, client_info, arguments):
		'''
		Dispatch to local handler
		'''
		return await self.increment_vibe_motor()


	async def close(self):
		'''
		Cancel all registered tasks and close window.
		'''
		self.stopped = True

		if self.server:
			logging.debug('closing socket window - stopping server')
			self.server.stop()
		
		if self.server_thread:
			while self.server_thread.is_alive():
				logging.debug('closing socket window - waiting for thread to stop')
				time.sleep(1)

		logging.debug('closing socket window - closing parent')
		await super(GUISampleWithSocket, self).close()

		logging.debug('closing socket window - done')


if __name__ == '__main__':
		
	# Configure logging to a basic level
	logging.basicConfig(format='%(asctime)s - %(thread)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)
	
	# Configure logging for the library
	logging.getLogger(f1client.Constants.LOGGER_NAME).setLevel(logging.INFO)
	logging.getLogger(f1client.Constants.LOGGER_IO_NAME).setLevel(logging.WARN)
	logging.getLogger(f1client.Constants.LOGGER_CALLBACK_NAME).setLevel(logging.INFO)
	logging.getLogger(f1client.Constants.LOGGER_SOCKET_SERVER_NAME).setLevel(logging.DEBUG)
	
	# Configure logging for the backend BLE adapter (bleak)
	logging.getLogger('bleak').setLevel(logging.INFO)

	# Run the sample in asyncio event loop
	loop = asyncio.get_event_loop()
	app = GUISampleWithSocket(loop)
	loop.run_forever()
	loop.close()
