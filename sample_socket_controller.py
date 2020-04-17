import asyncio
import logging
import socket
import json
import re
import getpass
import PySimpleGUI as sg

import lelof1py as f1client

from sample_gui import GUISample

DEFAULT_NAME = getpass.getuser()
REMOTE_ADDR = '127.0.0.1'
REMOTE_PORT = 5005
SOCKET_ENCODING = 'utf8'


# Initialize context with service
class GUISampleSocketController(GUISample):
	'''
	Complete sample of device discovery, connection and control with simple GUI.
	Includes a socket server for remote control
	'''
	def __init__(self, loop, refresh_interval=1/100):
		self.remote_ip = None
		self.remote_port = None
		self.remote_name = None
		
		self.remote_connected = False
		self.remote_authorized = False
		
		super(GUISampleSocketController, self).__init__(loop, refresh_interval)

		self.fs_utils = f1client.FsUtils('GUISampleSocketController')

	
	def get_layout(self):
		'''
		Optionally edit the base layout of the superclass
		'''
		base_layout = super(GUISampleSocketController, self).get_layout()
		
		# Set GUI theme
		sg.theme('Dark Blue 7')
		
		return base_layout


	async def post_construct(self):
		'''
		Hide buttons that are visible in the main class
		'''
		self.window[self.EVENT_DISCOVER].update(visible=False)
		
		# Once done, ask for connection data

		await self.connect_to_remote()

		self.tasks.append(self.loop.create_task(self.sensor_status_updater(15)))


	def get_client(self):
		if not self.client:
			if self.remote_ip and self.remote_port:
				self.client = f1client.SocketClient(self.remote_ip, self.remote_port)

		return self.client


	async def is_connected(self):
		return self.client and self.client.is_connected() and self.remote_authorized and self.remote_connected


	async def is_authorized(self):
		v = self.client and (('authorized' in self.snapshot and self.snapshot['authorized']) or await self.client.is_authorized())
		self.snapshot['authorized'] = v
		return v


	async def discover(self, autoconnect=False):
		logging.debug('discover is suppressed.')


	async def subscribe_notifications(self):
		logging.debug('subscribe_notifications is suppressed.')


	async def connect_to_remote(self):
		
		last_profile = self.fs_utils.load_connection_profile(safe=True)
		def_name = last_profile.name if last_profile and last_profile.name else DEFAULT_NAME
		def_addr = last_profile.address.split(':')[0] if last_profile and last_profile.address else REMOTE_ADDR
		def_port = int(last_profile.address.split(':')[1]) if last_profile and last_profile.address else REMOTE_PORT
		
		window = sg.Window('Remote connection', [
			[sg.Text('Please enter data for remote connection.', pad=(0, 20))],
			[sg.Text('Your name:', pad=(0, 10)), sg.Input(def_name, key='FIELD_NAME', size=(15, 1))],
			[sg.Text('IP address:', pad=(0, 10)), sg.Input(def_addr, key='FIELD_IP', size=(15, 1))],
			[sg.Text('Port:', pad=(0, 10)), sg.Input(def_port, key='FIELD_PORT', size=(10, 1))],
			[sg.Button('CONNECT', key='connect', size=(10, None), pad=(5, 20)), sg.Button('Cancel', key='cancel', size=(6, None), pad=(5, 20))]
		])
		
		while True:
			window.refresh()
			event, values = window.read(timeout=10)
			
			if event is None or event != '__TIMEOUT__':
				if event is None or event == 'cancel':
					break
				elif event == 'connect':
					self.remote_ip = values['FIELD_IP']
					self.remote_port = int(values['FIELD_PORT'])
					self.remote_name = values['FIELD_NAME']
					break

			await asyncio.sleep(0.1)

		window.close()
		
		if self.remote_ip and self.remote_port:
			self.log('attempting connection to ' + self.remote_ip)
			self.schedule(self.connect())
		else:
			logging.warn('no connection data provided! quitting')
			self.loop.create_task(self.close())


	async def connect(self):
		'''
		Attempts connection to the specified IP:PORT
		'''
		if not self.get_client().is_connected():
			self.update_status('connecting to remote host ...')
			await self.get_client().connect()
			
		if self.remote_name:
			self.update_status('sending user identifier ...')
			await self.get_client().set_name(self.remote_name)
		
		self.update_status('waiting for authorization ...')
		await self.get_client().request_remote_authorization()

		while True:
			r = await self.get_client().get_remote_authorization()
			if r == 'BLOCKED':
				logging.warning('server DID NOT AUTHORIZE this client.')
				self.loop.create_task(self.close())
				return
			elif not r:
				self.update_status('waiting for user to authorize connection...')
				await asyncio.sleep(5)
			else:
				break
		
		self.remote_authorized = True
		
		while not await self.get_client().is_remote_connected():
			self.update_status('waiting for user to connect to device...')
			await asyncio.sleep(5)
		
		while not await self.get_client().get_key_state():
			self.update_status('waiting for user to confirm device connection...')
			await asyncio.sleep(5)
		
		self.remote_connected = True
		
		await self.get_client().stop_motors()
		self.update_status('connected to device')
		
		# Save connection profile to disk
		profile = f1client.ConnectionProfile()
		profile.address = self.remote_ip + ':' + str(self.remote_port)
		profile.uuid = 'not-supported (' + profile.address + ')'
		profile.name = self.remote_name
		
		self.fs_utils.save_connection_profile(profile, safe=True)
	
		# Lock device for exclusive access
		await self.get_client().send_command('lock')
		
		# Read device info
		await self.refresh_status()


	async def disconnect(self):
		'''
		Disconnects from device. 
		If device is connected and authorization has been gived, the device is shutdown.
		'''
		self.update_status('disconnecting from device')

		if self.get_client().is_connected():
			if await self.get_client().is_authorized():
				self.update_status('releasing lock')
				await self.get_client().send_command('unlock')
		
				self.update_status('shutting down connection')
				await self.get_client().shutdown()
			self.update_status('closing connection')
			await self.get_client().disconnect()

		self.update_status('device disconnected')
		self.update(self.FIELD_DEVICE, 'no device')
		self.window[self.FIELD_BATTERY].update_bar(0)

		self.client = None


	async def refresh_sensor_status(self):
		self.snapshot = await self.get_client().send_command('get_status_snapshot')
		
		await super(GUISampleSocketController, self).refresh_sensor_status()
		
				
if __name__ == '__main__':
		
	# Configure logging to a basic level
	logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)
	
	# Configure logging for the library
	logging.getLogger(f1client.Constants.LOGGER_NAME).setLevel(logging.INFO)
	logging.getLogger(f1client.Constants.LOGGER_IO_NAME).setLevel(logging.DEBUG)
	logging.getLogger(f1client.Constants.LOGGER_CALLBACK_NAME).setLevel(logging.INFO)
	
	# Configure logging for the backend BLE adapter (bleak)
	logging.getLogger('bleak').setLevel(logging.INFO)

	# Run the sample in asyncio event loop
	loop = asyncio.get_event_loop()
	app = GUISampleSocketController(loop)
	loop.run_forever()
	loop.close()
